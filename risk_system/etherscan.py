"""Rate-limited Etherscan V2 client with key rotation and retry handling."""

from __future__ import annotations

import itertools
import os
import random
import threading
import time
from collections.abc import Callable
from typing import Any

import requests


class EtherscanError(RuntimeError):
    """Base error for an Etherscan request."""


class EtherscanConfigurationError(EtherscanError):
    """Raised when no API key is configured."""


class EtherscanRateLimitError(EtherscanError):
    """Raised when Etherscan continues to throttle after retries."""


def configured_api_keys() -> list[str]:
    """Return unique configured keys without ever logging their values."""
    candidates = [os.getenv("ETHERSCAN_API_KEY", "")]
    candidates.extend(os.getenv(f"ETHERSCAN_API_KEY_V{i}", "") for i in range(5))
    return list(dict.fromkeys(value.strip() for value in candidates if value.strip()))


class EtherscanClient:
    """Small synchronous client for the documented Etherscan V2 API."""

    base_url = "https://api.etherscan.io/v2/api"

    def __init__(
        self,
        api_keys: list[str] | None = None,
        *,
        chain_id: int = 1,
        calls_per_second_per_key: float | None = None,
        timeout: float = 25.0,
        max_retries: int = 6,
        progress: Callable[[str], None] | None = None,
    ) -> None:
        self.api_keys = api_keys or configured_api_keys()
        if not self.api_keys:
            raise EtherscanConfigurationError(
                "Set ETHERSCAN_API_KEY or ETHERSCAN_API_KEY_V0..V4 in the local .env file."
            )
        self.chain_id = chain_id
        self.timeout = timeout
        self.max_retries = max_retries
        self.progress = progress
        configured_rate = float(os.getenv("ETHERSCAN_CALLS_PER_SECOND_PER_KEY", "2.5"))
        self.calls_per_second_per_key = calls_per_second_per_key or configured_rate
        self._key_cycle = itertools.cycle(range(len(self.api_keys)))
        self._last_call = [0.0] * len(self.api_keys)
        self._lock = threading.Lock()
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Stablecoin-Risk-System/3.0"})

    def _next_key(self) -> tuple[int, str]:
        with self._lock:
            index = next(self._key_cycle)
            minimum_interval = 1.0 / max(self.calls_per_second_per_key, 0.1)
            wait_for = minimum_interval - (time.monotonic() - self._last_call[index])
            if wait_for > 0:
                time.sleep(wait_for)
            self._last_call[index] = time.monotonic()
            return index, self.api_keys[index]

    @staticmethod
    def _is_rate_limited(response: requests.Response, payload: Any) -> bool:
        if response.status_code == 429:
            return True
        if isinstance(payload, dict):
            result = str(payload.get("result", "")).lower()
            message = str(payload.get("message", "")).lower()
            return "rate limit" in result or "rate limit" in message
        return False

    def request(self, *, module: str, action: str, **params: Any) -> Any:
        """Call one endpoint and return its result field."""
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            _, api_key = self._next_key()
            query = {
                "chainid": str(self.chain_id),
                "module": module,
                "action": action,
                "apikey": api_key,
                **params,
            }
            try:
                response = self.session.get(self.base_url, params=query, timeout=self.timeout)
                payload = response.json()
                if self._is_rate_limited(response, payload):
                    retry_after = response.headers.get("Retry-After")
                    base_wait = float(retry_after) if retry_after else min(30.0, 2**attempt)
                    wait_for = base_wait + random.uniform(0.0, 0.25)
                    if self.progress:
                        self.progress(f"Etherscan throttled the collector; retrying in {wait_for:.1f}s")
                    time.sleep(wait_for)
                    continue
                response.raise_for_status()
                if not isinstance(payload, dict):
                    raise EtherscanError("Etherscan returned a non-object response")
                result = payload.get("result")
                if payload.get("status") == "0" and isinstance(result, str):
                    if "no transactions found" in result.lower() or "no records found" in result.lower():
                        return []
                    raise EtherscanError(result)
                return result
            except (requests.RequestException, ValueError, EtherscanError) as exc:
                last_error = exc
                if attempt + 1 < self.max_retries:
                    time.sleep(min(30.0, 2**attempt) + random.uniform(0.0, 0.25))
        if isinstance(last_error, EtherscanError):
            raise last_error
        raise EtherscanError(f"Etherscan request failed after {self.max_retries} attempts: {last_error}")

    def token_transfers(
        self,
        address: str,
        *,
        contract_address: str | None = None,
        offset: int = 100,
        page: int = 1,
        sort: str = "desc",
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "address": address,
            "page": page,
            "offset": min(max(offset, 1), 1000),
            "sort": sort,
        }
        if contract_address:
            params["contractaddress"] = contract_address
        result = self.request(module="account", action="tokentx", **params)
        return result if isinstance(result, list) else []

    def latest_block(self) -> int:
        result = self.request(module="proxy", action="eth_blockNumber")
        if not isinstance(result, str):
            raise EtherscanError("Latest block response did not contain a hexadecimal block number")
        return int(result, 16)

    def transfer_logs(
        self,
        contract_address: str,
        from_block: int,
        to_block: int,
        *,
        offset: int = 1000,
    ) -> list[dict[str, Any]]:
        result = self.request(
            module="logs",
            action="getLogs",
            address=contract_address,
            fromBlock=from_block,
            toBlock=to_block,
            topic0="0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
            page=1,
            offset=min(max(offset, 1), 1000),
        )
        return result if isinstance(result, list) else []
