"""Canonical feature schema shared by collection, training, and inference."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any

import numpy as np

FEATURE_COLUMNS = [
    "wallet_age_days",
    "avg_tx",
    "recent_tx",
    "tx_frequency",
    "tx_per_min",
    "tx_per_hour",
    "tx_per_day",
    "avg_time_between_tx_sec",
    "dust_tx_ratio",
    "similarity_hits",
    "new_sender_ratio",
    "is_poisoned_pattern",
    "tiny_tx_count",
    "unique_receivers",
    "avg_tx_value",
    "window_days",
    "repeat_small_to_count",
    "no_meaningful_flow",
    "short_time_window",
]


def empty_features() -> dict[str, float]:
    return {name: 0.0 for name in FEATURE_COLUMNS}


def features_from_transfers(transfers: list[dict[str, Any]], wallet: str) -> dict[str, float]:
    """Generate the canonical behavioral features from ERC-20 transfers."""
    if not transfers:
        return empty_features()
    normalized_wallet = wallet.lower()
    parsed: list[tuple[int, float, str, str]] = []
    for transfer in transfers:
        try:
            timestamp = int(transfer.get("timeStamp", 0))
            decimals = int(transfer.get("tokenDecimal", 18) or 18)
            value = int(transfer.get("value", 0)) / (10**decimals)
            sender = str(transfer.get("from", "")).lower()
            recipient = str(transfer.get("to", "")).lower()
        except (TypeError, ValueError, OverflowError):
            continue
        if timestamp > 0:
            parsed.append((timestamp, value, sender, recipient))
    if not parsed:
        return empty_features()

    parsed.sort(key=lambda item: item[0])
    timestamps: np.ndarray = np.asarray([item[0] for item in parsed], dtype=float)
    values: np.ndarray = np.asarray([item[1] for item in parsed], dtype=float)
    now = datetime.now(UTC).timestamp()
    duration_seconds = max(float(timestamps[-1] - timestamps[0]), 1.0)
    duration_days = max(duration_seconds / 86400.0, 1.0 / 86400.0)
    deltas = np.diff(timestamps)
    dust_mask = values <= 0.001
    incoming_senders = [
        sender for _, _, sender, recipient in parsed if recipient == normalized_wallet and sender
    ]
    outgoing_receivers = [
        recipient for _, _, sender, recipient in parsed if sender == normalized_wallet and recipient
    ]
    recipient_counts = Counter(outgoing_receivers)
    recent_cutoff = now - 86400.0
    recent_values = [value for timestamp, value, _, _ in parsed if timestamp >= recent_cutoff]
    tiny_recipients = [
        recipient
        for _, value, sender, recipient in parsed
        if sender == normalized_wallet and 0 < value <= 0.001 and recipient
    ]
    tiny_recipient_counts = Counter(tiny_recipients)
    repeat_small = sum(count for count in tiny_recipient_counts.values() if count >= 2)
    unique_senders = len(set(incoming_senders))
    new_sender_ratio = unique_senders / max(len(incoming_senders), 1)
    is_poisoned = float(len(tiny_recipients) >= 3 and repeat_small >= 2 and new_sender_ratio >= 0.5)
    wallet_age_days = max((now - timestamps[0]) / 86400.0, 0.0)
    avg_value = float(np.mean(values)) if len(values) else 0.0
    features = {
        "wallet_age_days": wallet_age_days,
        "avg_tx": avg_value,
        "recent_tx": float(np.mean(recent_values)) if recent_values else 0.0,
        "tx_frequency": float(len(parsed)),
        "tx_per_min": len(parsed) / max(duration_seconds / 60.0, 1.0),
        "tx_per_hour": len(parsed) / max(duration_seconds / 3600.0, 1.0),
        "tx_per_day": len(parsed) / duration_days,
        "avg_time_between_tx_sec": float(np.mean(deltas)) if len(deltas) else duration_seconds,
        "dust_tx_ratio": float(np.mean(dust_mask)),
        "similarity_hits": float(repeat_small),
        "new_sender_ratio": float(new_sender_ratio),
        "is_poisoned_pattern": is_poisoned,
        "tiny_tx_count": float(np.sum(dust_mask)),
        "unique_receivers": float(len(recipient_counts)),
        "avg_tx_value": avg_value,
        "window_days": duration_days,
        "repeat_small_to_count": float(repeat_small),
        "no_meaningful_flow": float(bool(len(values)) and float(np.max(values)) <= 0.001),
        "short_time_window": float(duration_seconds <= 3600.0),
    }
    return {name: float(features.get(name, 0.0)) for name in FEATURE_COLUMNS}
