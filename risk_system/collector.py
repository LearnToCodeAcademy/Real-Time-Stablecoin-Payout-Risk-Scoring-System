"""Resumable wallet-network collection for local model-data preparation."""

from __future__ import annotations

import csv
import json
import threading
import uuid
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from .contracts import TOKEN_CONTRACTS
from .etherscan import EtherscanClient
from .features import FEATURE_COLUMNS, features_from_transfers
from .reputation import load_local_risk_labels


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def valid_address(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 42 or not value.startswith("0x"):
        return False
    try:
        int(value[2:], 16)
    except ValueError:
        return False
    return True


@dataclass
class CollectionSettings:
    target_wallets: int = 1000
    tokens: list[str] = field(default_factory=lambda: ["USDT", "USDC"])
    seed_wallets: list[str] = field(default_factory=list)
    max_neighbors_per_wallet: int = 25
    transactions_per_wallet: int = 100
    resume: bool = True

    def validate(self) -> None:
        if self.target_wallets < 1 or self.target_wallets > 1_000_000:
            raise ValueError("target_wallets must be between 1 and 1,000,000")
        if self.max_neighbors_per_wallet < 1 or self.max_neighbors_per_wallet > 500:
            raise ValueError("max_neighbors_per_wallet must be between 1 and 500")
        if self.transactions_per_wallet < 1 or self.transactions_per_wallet > 1000:
            raise ValueError("transactions_per_wallet must be between 1 and 1,000")
        normalized = [token.upper() for token in self.tokens]
        unsupported = sorted(set(normalized) - set(TOKEN_CONTRACTS))
        if unsupported:
            raise ValueError(f"Unsupported collection tokens: {', '.join(unsupported)}")
        self.tokens = normalized
        self.seed_wallets = list(
            dict.fromkeys(value.lower() for value in self.seed_wallets if valid_address(value))
        )


@dataclass
class CollectionState:
    job_id: str
    status: str
    settings: dict
    discovered: int = 0
    processed: int = 0
    requests: int = 0
    empty_wallets: int = 0
    errors: int = 0
    started_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    finished_at: str | None = None
    message: str = "Queued"
    output_path: str | None = None
    checkpoint_path: str | None = None


class WalletCollector:
    """Breadth-first collector that checkpoints every processed wallet."""

    def __init__(
        self,
        settings: CollectionSettings,
        *,
        job_id: str | None = None,
        root: Path | str = Path("data/collections"),
        progress: Callable[[CollectionState], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> None:
        settings.validate()
        self.settings = settings
        self.job_id = job_id or uuid.uuid4().hex[:12]
        self.root = Path(root)
        self.job_dir = self.root / self.job_id
        self.checkpoint_path = self.job_dir / "checkpoint.json"
        self.output_path = self.job_dir / "wallets.csv"
        self.features_path = self.job_dir / "features.csv"
        self.processed_path = self.job_dir / "processed.txt"
        self.progress = progress
        self.cancel_event = cancel_event or threading.Event()
        self.state = CollectionState(
            job_id=self.job_id,
            status="queued",
            settings=asdict(settings),
            output_path=str(self.output_path),
            checkpoint_path=str(self.checkpoint_path),
        )
        self.trusted_risk_labels = load_local_risk_labels()
        self.client = EtherscanClient(progress=self._progress_message)

    def _progress_message(self, message: str) -> None:
        self.state.message = message
        self._persist_state()

    def _persist_state(self) -> None:
        self.state.updated_at = utc_now()
        self.job_dir.mkdir(parents=True, exist_ok=True)
        temporary = self.job_dir / "checkpoint.tmp"
        temporary.write_text(json.dumps(asdict(self.state), indent=2), encoding="utf-8")
        temporary.replace(self.checkpoint_path)
        if self.progress:
            self.progress(self.state)

    @staticmethod
    def default_seeds(limit: int = 100) -> list[str]:
        seeds: list[str] = []
        for candidate in (Path("wallet_pool.csv"), Path("v4_wallet_pool.csv")):
            if not candidate.exists():
                continue
            with candidate.open("r", encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    wallet = str(row.get("wallet", "")).lower()
                    if valid_address(wallet) and wallet not in seeds:
                        seeds.append(wallet)
                        if len(seeds) >= limit:
                            return seeds
        return seeds

    def _load_resume_data(self) -> tuple[set[str], deque[str]]:
        visited: set[str] = set()
        frontier: deque[str] = deque()
        if self.settings.resume and self.output_path.exists():
            with self.output_path.open("r", encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    wallet = str(row.get("wallet", "")).lower()
                    if valid_address(wallet):
                        visited.add(wallet)
        processed: set[str] = set()
        if self.settings.resume and self.processed_path.exists():
            processed = {
                value.strip().lower()
                for value in self.processed_path.read_text(encoding="utf-8").splitlines()
                if valid_address(value.strip().lower())
            }
        seeds = self.settings.seed_wallets or self.default_seeds()
        for wallet in seeds:
            if wallet not in visited:
                visited.add(wallet)
                self._append_wallet(wallet, "seed", "MULTI", 0)
        for wallet in visited:
            if wallet not in processed:
                frontier.append(wallet)
        return visited, frontier

    def _append_wallet(self, wallet: str, source: str, token: str, depth: int) -> None:
        new_file = not self.output_path.exists()
        self.job_dir.mkdir(parents=True, exist_ok=True)
        with self.output_path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "wallet",
                    "source_wallet",
                    "token",
                    "depth",
                    "label",
                    "label_source",
                    "collected_at",
                ],
            )
            if new_file:
                writer.writeheader()
            writer.writerow(
                {
                    "wallet": wallet,
                    "source_wallet": source,
                    "token": token,
                    "depth": depth,
                    "label": 1 if wallet in self.trusted_risk_labels else -1,
                    "label_source": self.trusted_risk_labels.get(wallet, "unlabeled"),
                    "collected_at": utc_now(),
                }
            )

    def _append_features(self, wallet: str, token: str, transfers: list[dict]) -> None:
        new_file = not self.features_path.exists()
        record = {
            "wallet": wallet,
            "token": token,
            "label": 1 if wallet in self.trusted_risk_labels else -1,
            "label_source": self.trusted_risk_labels.get(wallet, "unlabeled"),
            "source": f"collection:{self.job_id}",
            **features_from_transfers(transfers, wallet),
        }
        with self.features_path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["wallet", "token", "label", "label_source", "source", *FEATURE_COLUMNS],
            )
            if new_file:
                writer.writeheader()
            writer.writerow(record)

    def _mark_processed(self, wallet: str) -> None:
        with self.processed_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{wallet}\n")

    def run(self) -> CollectionState:
        visited, frontier = self._load_resume_data()
        if not frontier:
            raise ValueError("No valid seeds are available; provide at least one wallet address")
        self.state.status = "running"
        self.state.discovered = len(visited)
        self.state.message = "Collector started"
        self._persist_state()

        depth_by_wallet = {wallet: 0 for wallet in frontier}
        try:
            while frontier and len(visited) < self.settings.target_wallets:
                if self.cancel_event.is_set():
                    self.state.status = "cancelled"
                    self.state.message = "Collection cancelled; checkpoint preserved"
                    break
                wallet = frontier.popleft()
                depth = depth_by_wallet.get(wallet, 0)
                found_for_wallet = 0
                for token in self.settings.tokens:
                    contract = TOKEN_CONTRACTS[token]["address"]
                    try:
                        transfers = self.client.token_transfers(
                            wallet,
                            contract_address=contract,
                            offset=self.settings.transactions_per_wallet,
                        )
                        self.state.requests += 1
                        if transfers:
                            self._append_features(wallet, token, transfers)
                    except Exception as exc:
                        self.state.errors += 1
                        self.state.message = f"Request failed for {wallet[:10]}: {exc}"
                        continue
                    neighbors: list[str] = []
                    for transfer in transfers:
                        for field_name in ("from", "to"):
                            neighbor = str(transfer.get(field_name, "")).lower()
                            if valid_address(neighbor) and neighbor != wallet and neighbor not in visited:
                                neighbors.append(neighbor)
                    for neighbor in list(dict.fromkeys(neighbors))[: self.settings.max_neighbors_per_wallet]:
                        visited.add(neighbor)
                        frontier.append(neighbor)
                        depth_by_wallet[neighbor] = depth + 1
                        self._append_wallet(neighbor, wallet, token, depth + 1)
                        found_for_wallet += 1
                        if len(visited) >= self.settings.target_wallets:
                            break
                    if len(visited) >= self.settings.target_wallets:
                        break
                self.state.processed += 1
                self._mark_processed(wallet)
                self.state.discovered = len(visited)
                if found_for_wallet == 0:
                    self.state.empty_wallets += 1
                self.state.message = (
                    f"Processed {self.state.processed:,}; discovered {self.state.discovered:,} "
                    f"of {self.settings.target_wallets:,} wallets"
                )
                self._persist_state()
            else:
                if self.state.status == "running":
                    self.state.status = "success"
                    self.state.message = (
                        f"Collection finished with {self.state.discovered:,} wallets and "
                        f"{self.state.requests:,} API requests"
                    )
        except Exception as exc:
            self.state.status = "failed"
            self.state.errors += 1
            self.state.message = str(exc)
        self.state.finished_at = utc_now()
        self._persist_state()
        return self.state
