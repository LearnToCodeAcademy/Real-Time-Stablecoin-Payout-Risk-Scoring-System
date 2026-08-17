"""Durable Postgres feature/label storage with an optional Redis fast layer."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

import psycopg2
from dotenv import load_dotenv

try:
    import redis
except ImportError:
    redis = None


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
REDIS_URL = os.getenv("REDIS_URL", "").strip()
FEATURE_CACHE_TTL = int(os.getenv("FEATURE_CACHE_TTL_SECONDS", "600"))

conn = None
cursor = None
redis_client = None
db_lock = threading.RLock()


def _initialize_schema() -> None:
    if conn is None:
        return
    with db_lock, conn.cursor() as active_cursor:
        active_cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS wallet_features (
                wallet TEXT NOT NULL,
                token TEXT NOT NULL,
                wallet_age_days DOUBLE PRECISION NOT NULL DEFAULT 0,
                avg_tx DOUBLE PRECISION NOT NULL DEFAULT 0,
                recent_tx DOUBLE PRECISION NOT NULL DEFAULT 0,
                tx_frequency DOUBLE PRECISION NOT NULL DEFAULT 0,
                tx_per_min DOUBLE PRECISION NOT NULL DEFAULT 0,
                tx_per_hour DOUBLE PRECISION NOT NULL DEFAULT 0,
                tx_per_day DOUBLE PRECISION NOT NULL DEFAULT 0,
                avg_time_between_tx_sec DOUBLE PRECISION NOT NULL DEFAULT 0,
                feature_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                timestamp BIGINT NOT NULL,
                PRIMARY KEY (wallet, token)
            );
            CREATE TABLE IF NOT EXISTS wallet_labels (
                wallet TEXT PRIMARY KEY,
                label INTEGER NOT NULL,
                trusted BOOLEAN NOT NULL DEFAULT FALSE,
                updated_at BIGINT NOT NULL
            );
            """
        )
        conn.commit()


if DATABASE_URL:
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=5)
        conn.autocommit = False
        _initialize_schema()
    except Exception:
        conn = None
else:
    conn = None

if REDIS_URL and redis:
    try:
        redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        redis_client.ping()
    except Exception:
        redis_client = None


def health_status() -> dict[str, str]:
    database = "disabled"
    if conn is not None:
        try:
            with db_lock, conn.cursor() as active_cursor:
                active_cursor.execute("SELECT 1")
                active_cursor.fetchone()
            database = "connected"
        except Exception:
            database = "error"
    cache = "disabled"
    if redis_client is not None:
        try:
            redis_client.ping()
            cache = "connected"
        except Exception:
            cache = "error"
    return {"database": database, "redis": cache}


def _feature_key(wallet: str, token: str) -> str:
    return f"features:{token.upper()}:{wallet.lower()}"


def get_features(wallet: str, token: str) -> dict[str, Any] | None:
    key = _feature_key(wallet, token)
    if redis_client is not None:
        try:
            cached = redis_client.get(key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass
    if conn is None:
        return None
    try:
        with db_lock, conn.cursor() as active_cursor:
            active_cursor.execute(
                """
                SELECT feature_json
                FROM wallet_features
                WHERE wallet=%s AND token=%s
                """,
                (wallet.lower(), token.upper()),
            )
            row = active_cursor.fetchone()
        if not row:
            return None
        result = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        if redis_client is not None:
            try:
                redis_client.setex(key, FEATURE_CACHE_TTL, json.dumps(result))
            except Exception:
                pass
        return result
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return None


def save_features(wallet: str, token: str, features: dict[str, Any]) -> None:
    normalized = {
        key: float(value) if isinstance(value, (int, float)) else value for key, value in features.items()
    }
    if redis_client is not None:
        try:
            redis_client.setex(_feature_key(wallet, token), FEATURE_CACHE_TTL, json.dumps(normalized))
        except Exception:
            pass
    if conn is None:
        return
    try:
        with db_lock, conn.cursor() as active_cursor:
            active_cursor.execute(
                """
                INSERT INTO wallet_features (
                    wallet, token, wallet_age_days, avg_tx, recent_tx,
                    tx_frequency, tx_per_min, tx_per_hour, tx_per_day,
                    avg_time_between_tx_sec, feature_json, timestamp
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
                ON CONFLICT (wallet, token) DO UPDATE SET
                    wallet_age_days=EXCLUDED.wallet_age_days,
                    avg_tx=EXCLUDED.avg_tx,
                    recent_tx=EXCLUDED.recent_tx,
                    tx_frequency=EXCLUDED.tx_frequency,
                    tx_per_min=EXCLUDED.tx_per_min,
                    tx_per_hour=EXCLUDED.tx_per_hour,
                    tx_per_day=EXCLUDED.tx_per_day,
                    avg_time_between_tx_sec=EXCLUDED.avg_time_between_tx_sec,
                    feature_json=EXCLUDED.feature_json,
                    timestamp=EXCLUDED.timestamp
                """,
                (
                    wallet.lower(),
                    token.upper(),
                    normalized.get("wallet_age_days", 0),
                    normalized.get("avg_tx", 0),
                    normalized.get("recent_tx", 0),
                    normalized.get("tx_frequency", 0),
                    normalized.get("tx_per_min", 0),
                    normalized.get("tx_per_hour", 0),
                    normalized.get("tx_per_day", 0),
                    normalized.get("avg_time_between_tx_sec", 0),
                    json.dumps(normalized),
                    int(time.time()),
                ),
            )
            conn.commit()
    except Exception:
        conn.rollback()


def get_label(wallet: str) -> dict[str, Any] | None:
    if conn is None:
        return None
    try:
        with db_lock, conn.cursor() as active_cursor:
            active_cursor.execute(
                "SELECT label, trusted FROM wallet_labels WHERE wallet=%s",
                (wallet.lower(),),
            )
            row = active_cursor.fetchone()
        return {"label": int(row[0]), "trusted": bool(row[1])} if row else None
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return None


def save_label(wallet: str, label: int, trusted: bool) -> None:
    if label not in {0, 1, 2}:
        raise ValueError("label must be 0 (safe), 1 (malicious), or 2 (poisoned)")
    if conn is None:
        return
    try:
        with db_lock, conn.cursor() as active_cursor:
            active_cursor.execute(
                """
                INSERT INTO wallet_labels (wallet, label, trusted, updated_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (wallet) DO UPDATE SET
                    label=EXCLUDED.label,
                    trusted=EXCLUDED.trusted,
                    updated_at=EXCLUDED.updated_at
                """,
                (wallet.lower(), label, trusted, int(time.time())),
            )
            conn.commit()
    except Exception:
        conn.rollback()
