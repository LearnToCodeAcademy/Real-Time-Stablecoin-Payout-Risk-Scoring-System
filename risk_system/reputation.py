"""Provider-backed wallet reputation screening that runs before behavioral ML."""

from __future__ import annotations

import csv
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

from .etherscan import EtherscanClient, configured_api_keys

RISK_TERMS = {
    "phish",
    "hack",
    "scam",
    "exploit",
    "sanction",
    "heist",
    "drainer",
    "stolen",
    "ransomware",
    "malicious",
    "fraud",
}


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except json.JSONDecodeError:
        pass
    return [item.strip() for item in text.replace(";", ",").split(",") if item.strip()]


def _is_risky(record: dict[str, Any]) -> bool:
    try:
        if int(record.get("reputation", 0)) >= 2:
            return True
    except (TypeError, ValueError):
        pass
    text = " ".join(
        [
            str(record.get("nametag", "")),
            str(record.get("notes_1", "")),
            str(record.get("shortdescription", "")),
            *(_as_list(record.get("labels"))),
            *(_as_list(record.get("labels_slug"))),
        ]
    ).lower()
    return any(term in text for term in RISK_TERMS)


class ReputationService:
    """Aggregate local and opt-in remote threat-intelligence providers."""

    def __init__(self) -> None:
        self.timeout = float(os.getenv("THREAT_INTEL_TIMEOUT_SECONDS", "8"))
        self.ttl = int(os.getenv("THREAT_INTEL_CACHE_TTL_SECONDS", "900"))
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._lock = threading.Lock()

    def _local_files(self) -> list[Path]:
        configured = [
            Path(value.strip())
            for value in os.getenv("THREAT_INTEL_FILES", "").split(os.pathsep)
            if value.strip()
        ]
        discovered = list(Path("threat_intel").glob("*.csv")) + list(Path("data/threat_intel").glob("*.csv"))
        return list(dict.fromkeys(path for path in [*configured, *discovered] if path.exists()))

    def _screen_local(self, address: str) -> tuple[list[dict[str, Any]], list[str]]:
        findings: list[dict[str, Any]] = []
        checked: list[str] = []
        for path in self._local_files():
            try:
                with path.open("r", encoding="utf-8-sig", newline="") as handle:
                    sample = handle.read(4096)
                    handle.seek(0)
                    try:
                        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
                    except csv.Error:
                        dialect = csv.excel
                    reader = csv.DictReader(handle, dialect=dialect)
                    if not reader.fieldnames or "address" not in {
                        str(name).lower().strip() for name in reader.fieldnames
                    }:
                        continue
                    checked.append(f"file:{path.name}")
                    for row in reader:
                        if str(row.get("address", "")).lower().strip() != address:
                            continue
                        risky = _is_risky(row) or str(row.get("decision", "")).upper() == "BLOCK"
                        findings.append(
                            {
                                "source": row.get("source") or f"local:{path.name}",
                                "risky": risky,
                                "nametag": row.get("nametag") or row.get("name") or "",
                                "labels": _as_list(row.get("labels") or row.get("category")),
                                "reason": row.get("reason")
                                or row.get("notes_1")
                                or "Imported threat-intelligence match",
                                "reputation": row.get("reputation"),
                            }
                        )
            except (OSError, csv.Error, UnicodeError):
                continue
        return findings, checked

    def _screen_etherscan(self, address: str) -> tuple[list[dict[str, Any]], list[str], list[str]]:
        if os.getenv("ENABLE_ETHERSCAN_METADATA", "false").lower() not in {"1", "true", "yes", "on"}:
            return [], [], []
        keys = configured_api_keys()
        if not keys:
            return [], [], ["etherscan_metadata: no Etherscan key configured"]
        findings: list[dict[str, Any]] = []
        checked: list[str] = []
        errors: list[str] = []
        chain_ids = [
            int(value.strip())
            for value in os.getenv("THREAT_INTEL_CHAIN_IDS", "1,137").split(",")
            if value.strip()
        ]
        for chain_id in chain_ids:
            provider = f"etherscan_metadata:{chain_id}"
            try:
                result = EtherscanClient(api_keys=keys, chain_id=chain_id).request(
                    module="nametag", action="getaddresstag", address=address
                )
                checked.append(provider)
                for row in result if isinstance(result, list) else []:
                    findings.append(
                        {
                            "source": provider,
                            "risky": _is_risky(row),
                            "nametag": row.get("nametag", ""),
                            "labels": _as_list(row.get("labels")),
                            "reason": row.get("notes_1")
                            or row.get("shortdescription")
                            or "Etherscan metadata match",
                            "reputation": row.get("reputation"),
                        }
                    )
            except Exception as exc:
                errors.append(f"{provider}: {exc}")
        return findings, checked, errors

    def _screen_chainabuse(self, address: str) -> tuple[list[dict[str, Any]], list[str], list[str]]:
        username = os.getenv("CHAINABUSE_API_USERNAME", "").strip()
        password = os.getenv("CHAINABUSE_API_PASSWORD", "").strip()
        if not username or not password:
            return [], [], []
        provider = "chainabuse"
        try:
            response = requests.get(
                "https://api.chainabuse.com/v0/reports",
                params={"address": address, "checked": "true", "page": 1, "perPage": 50},
                auth=(username, password),
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            rows = (
                payload.get("content", payload.get("reports", [])) if isinstance(payload, dict) else payload
            )
            findings = []
            for row in rows if isinstance(rows, list) else []:
                findings.append(
                    {
                        "source": provider,
                        "risky": True,
                        "nametag": row.get("scamCategory", row.get("category", "Reported address")),
                        "labels": _as_list(row.get("scamCategory", row.get("category"))),
                        "reason": row.get("description") or "Verified Chainabuse report",
                        "reputation": row.get("confidenceScore"),
                    }
                )
            return findings, [provider], []
        except Exception as exc:
            return [], [], [f"{provider}: {exc}"]

    def _screen_explorer(self, address: str) -> tuple[list[dict[str, Any]], list[str], list[str]]:
        if os.getenv("ENABLE_EXPLORER_REPUTATION", "false").lower() not in {
            "1",
            "true",
            "yes",
            "on",
        }:
            return [], [], []
        provider = "etherscan_public_label"
        try:
            response = requests.get(
                f"https://etherscan.io/address/{address}",
                headers={"User-Agent": "Stablecoin-Risk-System/3.0 (+local reputation screening)"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            page = BeautifulSoup(response.text, "html.parser")
            visible_text = " ".join(page.get_text(" ", strip=True).split())
            normalized_text = visible_text.lower()
            title = page.title.get_text(" ", strip=True) if page.title else "Reported address"
            normalized_title = title.lower()
            warning_phrases = (
                "there are reports that this address was used in a phishing scam",
                "this address has been reported to be involved in a scam",
            )
            title_is_risky = any(
                term in normalized_title
                for term in ("fake_phishing", "fake phishing", "phish / hack", "scam alert")
            )
            if not title_is_risky and not any(phrase in normalized_text for phrase in warning_phrases):
                return [], [provider], []
            nametag = title.split("|", 1)[0].strip()
            return (
                [
                    {
                        "source": provider,
                        "risky": True,
                        "nametag": nametag,
                        "labels": ["Phish / Hack"],
                        "reason": "Etherscan displays a public phishing/scam warning for this address",
                        "reputation": 2,
                    }
                ],
                [provider],
                [],
            )
        except Exception as exc:
            return [], [], [f"{provider}: {exc}"]

    def screen(self, address: str) -> dict[str, Any]:
        normalized = address.lower().strip()
        with self._lock:
            cached = self._cache.get(normalized)
            if cached and cached[0] > time.monotonic():
                return {**cached[1], "cache_hit": True}

        local_findings, local_checked = self._screen_local(normalized)
        etherscan_findings, etherscan_checked, etherscan_errors = self._screen_etherscan(normalized)
        chainabuse_findings, chainabuse_checked, chainabuse_errors = self._screen_chainabuse(normalized)
        explorer_findings, explorer_checked, explorer_errors = self._screen_explorer(normalized)
        findings = [*local_findings, *etherscan_findings, *chainabuse_findings, *explorer_findings]
        risky_findings = [finding for finding in findings if finding.get("risky")]
        checked = [*local_checked, *etherscan_checked, *chainabuse_checked, *explorer_checked]
        result = {
            "status": "MATCH" if risky_findings else ("CLEAR" if checked else "UNAVAILABLE"),
            "findings": risky_findings,
            "providers_checked": checked,
            "provider_errors": [*etherscan_errors, *chainabuse_errors, *explorer_errors],
            "cache_hit": False,
        }
        with self._lock:
            self._cache[normalized] = (time.monotonic() + self.ttl, result)
        return result


reputation_service = ReputationService()


def sync_etherscan_gas_guzzler_labels(
    output: str | Path = "data/threat_intel/etherscan_gas_guzzlers.csv",
) -> dict[str, Any]:
    """Import only rows that Etherscan explicitly labels as phishing/scam risk."""
    response = requests.get(
        "https://etherscan.io/gastracker",
        headers={"User-Agent": "Stablecoin-Risk-System/3.0 (+local threat-label sync)"},
        timeout=float(os.getenv("THREAT_INTEL_TIMEOUT_SECONDS", "8")),
    )
    response.raise_for_status()
    page = BeautifulSoup(response.text, "html.parser")
    records: dict[str, dict[str, Any]] = {}
    for row in page.select("tr"):
        text = " ".join(row.get_text(" ", strip=True).split())
        lowered = text.lower()
        if not any(term in lowered for term in ("fake_phishing", "phish / hack", "scam", "hack")):
            continue
        address = ""
        for link in row.select('a[href^="/address/0x"]'):
            match = re.search(r"/address/(0x[a-fA-F0-9]{40})", str(link.get("href", "")))
            if match:
                address = match.group(1).lower()
                break
        if not address:
            continue
        name_match = re.search(r"(Fake_Phishing\w*|\S*Scam\S*|\S*Hack\S*)", text, re.IGNORECASE)
        records[address] = {
            "address": address,
            "nametag": name_match.group(1) if name_match else "Etherscan flagged address",
            "labels": "Phish / Hack",
            "labels_slug": "phish-hack",
            "reputation": 2,
            "source": "etherscan_gas_guzzlers",
            "reason": "Explicitly risk-labeled in Etherscan's current Gas Guzzlers table",
            "decision": "BLOCK",
        }
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    fields = [
        "address",
        "nametag",
        "labels",
        "labels_slug",
        "reputation",
        "source",
        "reason",
        "decision",
    ]
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records.values())
    temporary.replace(destination)
    reputation_service._cache.clear()
    return {"source": "https://etherscan.io/gastracker", "records": len(records), "output": str(destination)}


def load_local_risk_labels() -> dict[str, str]:
    """Return attributed malicious labels from imported local provider files."""
    labels: dict[str, str] = {}
    for path in reputation_service._local_files():
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                sample = handle.read(4096)
                handle.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=",;")
                except csv.Error:
                    dialect = csv.excel
                for row in csv.DictReader(handle, dialect=dialect):
                    address = str(row.get("address", "")).lower().strip()
                    if re.fullmatch(r"0x[a-f0-9]{40}", address) and (
                        _is_risky(row) or str(row.get("decision", "")).upper() == "BLOCK"
                    ):
                        labels[address] = str(row.get("source") or f"local:{path.name}")
        except OSError:
            continue
    return labels
