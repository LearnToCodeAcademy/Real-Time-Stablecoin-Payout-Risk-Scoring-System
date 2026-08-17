"""Real Ethereum transfer streaming, scored alerts, and persistent cases."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import uuid
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .contracts import CONTRACT_TO_TOKEN, TOKEN_CONTRACTS, TRANSFER_TOPIC
from .etherscan import EtherscanClient, configured_api_keys

try:
    import websockets as _websocket_client

    websocket_client: Any = _websocket_client
    HAS_WEBSOCKETS = True
except ImportError:
    websocket_client = None
    HAS_WEBSOCKETS = False


logger = logging.getLogger(__name__)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class AlertStore:
    """SQLite-backed event and case store shared by live and manual scoring."""

    def __init__(self, path: str | Path = "data/risk_system.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    wallet TEXT NOT NULL,
                    token TEXT,
                    decision TEXT NOT NULL,
                    score REAL,
                    tx_hash TEXT,
                    block_number INTEGER,
                    amount REAL,
                    source TEXT NOT NULL,
                    reason TEXT,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_events_decision ON events(decision, timestamp DESC);
                CREATE TABLE IF NOT EXISTS cases (
                    case_id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL,
                    wallet TEXT NOT NULL,
                    token TEXT,
                    decision TEXT NOT NULL,
                    score REAL,
                    status TEXT NOT NULL DEFAULT 'open',
                    assignee TEXT,
                    note TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(event_id) REFERENCES events(event_id)
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_cases_event ON cases(event_id);
                """
            )

    def add_event(self, event: dict[str, Any]) -> dict[str, Any]:
        event = dict(event)
        event.setdefault("event_id", uuid.uuid4().hex)
        event.setdefault("timestamp", utc_now())
        event.setdefault("source", "manual")
        event.setdefault("decision", "OBSERVED")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO events (
                    event_id, timestamp, wallet, token, decision, score, tx_hash,
                    block_number, amount, source, reason, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    timestamp=excluded.timestamp, wallet=excluded.wallet,
                    token=excluded.token, decision=excluded.decision,
                    score=excluded.score, tx_hash=excluded.tx_hash,
                    block_number=excluded.block_number, amount=excluded.amount,
                    source=excluded.source, reason=excluded.reason,
                    payload_json=excluded.payload_json
                """,
                (
                    event["event_id"],
                    event["timestamp"],
                    event["wallet"],
                    event.get("token"),
                    event["decision"],
                    event.get("score"),
                    event.get("tx_hash"),
                    event.get("block_number"),
                    event.get("amount"),
                    event["source"],
                    event.get("reason"),
                    json.dumps(event, separators=(",", ":"), default=str),
                ),
            )
            if event["decision"] in {"REVIEW", "BLOCK"}:
                now = utc_now()
                connection.execute(
                    """
                    INSERT INTO cases (
                        case_id, event_id, wallet, token, decision, score, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?)
                    ON CONFLICT(event_id) DO UPDATE SET
                        decision=excluded.decision, score=excluded.score, updated_at=excluded.updated_at
                    """,
                    (
                        f"case-{event['event_id']}",
                        event["event_id"],
                        event["wallet"],
                        event.get("token"),
                        event["decision"],
                        event.get("score"),
                        now,
                        now,
                    ),
                )
        return event

    def recent_events(self, limit: int = 100, decision: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT payload_json FROM events"
        values: list[Any] = []
        if decision:
            query += " WHERE decision = ?"
            values.append(decision.upper())
        query += " ORDER BY timestamp DESC LIMIT ?"
        values.append(min(max(limit, 1), 1000))
        with self._connect() as connection:
            return [json.loads(row["payload_json"]) for row in connection.execute(query, values)]

    def cases(self, limit: int = 100, status: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM cases"
        values: list[Any] = []
        if status:
            query += " WHERE status = ?"
            values.append(status)
        query += " ORDER BY updated_at DESC LIMIT ?"
        values.append(min(max(limit, 1), 1000))
        with self._connect() as connection:
            return [dict(row) for row in connection.execute(query, values)]

    def update_case(
        self, case_id: str, status: str, assignee: str | None, note: str | None
    ) -> dict[str, Any]:
        if status not in {"open", "reviewed", "dismissed", "escalated"}:
            raise ValueError("Invalid case status")
        with self._connect() as connection:
            connection.execute(
                "UPDATE cases SET status=?, assignee=?, note=?, updated_at=? WHERE case_id=?",
                (status, assignee, note, utc_now(), case_id),
            )
            row = connection.execute("SELECT * FROM cases WHERE case_id=?", (case_id,)).fetchone()
        if row is None:
            raise KeyError(case_id)
        return dict(row)

    def statistics(self) -> dict[str, Any]:
        with self._connect() as connection:
            decision_counts = {
                row["decision"]: int(row["count"])
                for row in connection.execute(
                    "SELECT decision, COUNT(*) AS count FROM events GROUP BY decision"
                )
            }
            open_cases = int(
                connection.execute("SELECT COUNT(*) FROM cases WHERE status='open'").fetchone()[0]
            )
            top_wallets = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT wallet, token, COUNT(*) AS alerts, MAX(score) AS max_score,
                           MAX(timestamp) AS last_seen
                    FROM events
                    WHERE decision IN ('REVIEW', 'BLOCK')
                    GROUP BY wallet, token
                    ORDER BY max_score DESC, alerts DESC
                    LIMIT 10
                    """
                )
            ]
        return {"decisions": decision_counts, "open_cases": open_cases, "top_risky_wallets": top_wallets}


class LiveEventBroker:
    """Connect a real chain source to browser subscribers and persistent cases."""

    def __init__(
        self,
        store: AlertStore,
        scorer: Callable[[str, str], dict[str, Any]] | None = None,
    ) -> None:
        self.store = store
        self.scorer = scorer
        self.subscribers: set[asyncio.Queue] = set()
        self.task: asyncio.Task | None = None
        self.stop_event = asyncio.Event()
        self.score_semaphore = asyncio.Semaphore(1)
        self.recent_wallets: deque[str] = deque(maxlen=500)
        self.status: dict[str, Any] = {
            "state": "stopped",
            "source": None,
            "last_event_at": None,
            "last_block": None,
            "events_seen": 0,
            "events_scored": 0,
            "error": None,
        }

    async def start(self) -> None:
        if self.task and not self.task.done():
            return
        self.stop_event.clear()
        provider_url = (
            os.getenv("ALCHEMY_WS_URL", "").strip()
            or os.getenv("INFURA_WS_URL", "").strip()
            or os.getenv("ETH_RPC_WS_URL", "").strip()
        )
        if provider_url and HAS_WEBSOCKETS:
            self.status.update(state="connecting", source="websocket", error=None)
            self.task = asyncio.create_task(self._run_websocket(provider_url))
        elif configured_api_keys():
            self.status.update(state="connecting", source="etherscan", error=None)
            self.task = asyncio.create_task(self._run_etherscan())
        else:
            self.status.update(
                state="offline",
                source=None,
                error="Configure ALCHEMY_WS_URL, INFURA_WS_URL, ETH_RPC_WS_URL, or ETHERSCAN_API_KEY",
            )

    async def stop(self) -> None:
        self.stop_event.set()
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        self.status["state"] = "stopped"

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=250)
        self.subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self.subscribers.discard(queue)

    async def publish(self, event: dict[str, Any]) -> None:
        saved = await asyncio.to_thread(self.store.add_event, event)
        self.status["last_event_at"] = saved["timestamp"]
        self.status["events_seen"] += 1
        for queue in list(self.subscribers):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(saved)

    @staticmethod
    def _parse_log(log: dict[str, Any], source: str) -> dict[str, Any] | None:
        try:
            contract = str(log.get("address", "")).lower()
            token = CONTRACT_TO_TOKEN.get(contract)
            topics = log.get("topics") or []
            if not token or len(topics) < 3 or str(topics[0]).lower() != TRANSFER_TOPIC:
                return None
            sender = "0x" + str(topics[1])[-40:].lower()
            recipient = "0x" + str(topics[2])[-40:].lower()
            amount = int(str(log.get("data", "0x0")), 16) / (10 ** int(TOKEN_CONTRACTS[token]["decimals"]))
            tx_hash = str(log.get("transactionHash", ""))
            log_index = str(log.get("logIndex", "0x0"))
            block_value = log.get("blockNumber", 0)
            block_number = int(block_value, 16) if isinstance(block_value, str) else int(block_value)
            timestamp_value = log.get("timeStamp")
            if timestamp_value:
                timestamp_int = (
                    int(timestamp_value, 16) if isinstance(timestamp_value, str) else int(timestamp_value)
                )
                timestamp = datetime.fromtimestamp(timestamp_int, UTC).isoformat()
            else:
                timestamp = utc_now()
            return {
                "event_id": f"{tx_hash}:{log_index}",
                "timestamp": timestamp,
                "wallet": recipient,
                "from_wallet": sender,
                "token": token,
                "decision": "OBSERVED",
                "score": None,
                "reason": "Confirmed on-chain token transfer; risk scoring queued",
                "tx_hash": tx_hash,
                "block_number": block_number,
                "amount": amount,
                "source": source,
                "verified_real": True,
            }
        except (TypeError, ValueError, IndexError):
            return None

    async def _score_event(self, event: dict[str, Any]) -> None:
        if not self.scorer or event["wallet"] in self.recent_wallets:
            return
        self.recent_wallets.append(event["wallet"])
        async with self.score_semaphore:
            try:
                result = await asyncio.to_thread(self.scorer, event["wallet"], event["token"])
                scored = {
                    **event,
                    "decision": result.get("decision", "REVIEW"),
                    "score": result.get("score"),
                    "reason": result.get("reason", "Wallet scored from live transfer"),
                    "prob_normal": result.get("prob_normal"),
                    "prob_malicious": result.get("prob_malicious"),
                    "prob_poisoned": result.get("prob_poisoned"),
                    "scored_at": utc_now(),
                }
                self.status["events_scored"] += 1
                await self.publish(scored)
            except Exception as exc:
                logger.warning("Live wallet scoring failed: %s", exc)

    async def _handle_logs(self, logs: list[dict[str, Any]], source: str) -> None:
        score_limit = int(os.getenv("LIVE_SCORE_MAX_PER_BLOCK", "2"))
        scored = 0
        for log in logs[: int(os.getenv("LIVE_MAX_EVENTS_PER_BLOCK", "50"))]:
            event = self._parse_log(log, source)
            if not event:
                continue
            self.status["last_block"] = event["block_number"]
            await self.publish(event)
            if scored < score_limit:
                asyncio.create_task(self._score_event(event))
                scored += 1

    async def _run_etherscan(self) -> None:
        try:
            client = EtherscanClient()
            latest = await asyncio.to_thread(client.latest_block)
            current = latest - 1
            self.status.update(state="live", last_block=current, error=None)
            while not self.stop_event.is_set():
                latest = await asyncio.to_thread(client.latest_block)
                if latest > current:
                    for block in range(current + 1, latest + 1):
                        for metadata in TOKEN_CONTRACTS.values():
                            logs = await asyncio.to_thread(
                                client.transfer_logs, metadata["address"], block, block
                            )
                            await self._handle_logs(logs, "etherscan")
                        current = block
                        self.status["last_block"] = current
                await asyncio.sleep(float(os.getenv("ETHERSCAN_LIVE_POLL_SECONDS", "3")))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.status.update(state="error", error=str(exc))
            logger.exception("Etherscan live stream stopped")

    async def _run_websocket(self, provider_url: str) -> None:
        backoff = 1.0
        while not self.stop_event.is_set():
            try:
                async with websocket_client.connect(
                    provider_url, ping_interval=20, ping_timeout=20
                ) as socket:
                    for index, metadata in enumerate(TOKEN_CONTRACTS.values(), start=1):
                        await socket.send(
                            json.dumps(
                                {
                                    "jsonrpc": "2.0",
                                    "id": index,
                                    "method": "eth_subscribe",
                                    "params": [
                                        "logs",
                                        {"address": metadata["address"], "topics": [TRANSFER_TOPIC]},
                                    ],
                                }
                            )
                        )
                    self.status.update(state="live", source="websocket", error=None)
                    backoff = 1.0
                    while not self.stop_event.is_set():
                        message = json.loads(await asyncio.wait_for(socket.recv(), timeout=45))
                        log = message.get("params", {}).get("result")
                        if isinstance(log, dict):
                            await self._handle_logs([log], "websocket")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.status.update(state="reconnecting", error=str(exc))
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
