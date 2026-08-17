
import psycopg2
import time
import os
from dotenv import load_dotenv
from pathlib import Path

# =============================
# LOAD ENV
# =============================
BASE_DIR = Path(__file__).resolve().parent
env_path = BASE_DIR / ".env"

load_dotenv(dotenv_path=env_path)

DATABASE_URL = os.getenv("DATABASE_URL")

# Initialize connection/cursor as None so import won't fail when DB is unavailable
conn = None
cursor = None

if not DATABASE_URL:
    print("[WARN] DATABASE_URL not found; DB features disabled.")
else:
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        print("[OK] DB CONNECTED")
    except Exception as e:
        print(f"[WARN] DB connection failed: {e}")
        conn = None
        cursor = None

# =============================
# FEATURES
# =============================
def get_features(wallet, token):
    try:
        if cursor is None:
            return None
        cursor.execute("""
            SELECT wallet_age_days, avg_tx, recent_tx,
                   tx_frequency, tx_per_min, tx_per_hour,
                   tx_per_day, avg_time_between_tx_sec
            FROM wallet_features
            WHERE wallet=%s AND token=%s
        """, (wallet, token))

        row = cursor.fetchone()

        if not row:
            return None

        return {
            "wallet_age_days": int(row[0]),
            "avg_tx": float(row[1]),
            "recent_tx": float(row[2]),
            "tx_frequency": float(row[3]),
            "tx_per_min": float(row[4]),
            "tx_per_hour": float(row[5]),
            "tx_per_day": float(row[6]),
            "avg_time_between_tx_sec": float(row[7])
        }

    except Exception as e:
        print("[ERROR] DB fetch error:", e)
        return None


def save_features(wallet, token, f):
    try:
        if cursor is None or conn is None:
            print("[WARN] DB disabled; skipping save_features")
            return
        cursor.execute("""
            INSERT INTO wallet_features (
                wallet, token,
                wallet_age_days, avg_tx, recent_tx,
                tx_frequency, tx_per_min, tx_per_hour,
                tx_per_day, avg_time_between_tx_sec,
                timestamp
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (wallet, token)
            DO UPDATE SET
                wallet_age_days = EXCLUDED.wallet_age_days,
                avg_tx = EXCLUDED.avg_tx,
                recent_tx = EXCLUDED.recent_tx,
                tx_frequency = EXCLUDED.tx_frequency,
                tx_per_min = EXCLUDED.tx_per_min,
                tx_per_hour = EXCLUDED.tx_per_hour,
                tx_per_day = EXCLUDED.tx_per_day,
                avg_time_between_tx_sec = EXCLUDED.avg_time_between_tx_sec,
                timestamp = EXCLUDED.timestamp
        """, (
            wallet,
            token,
            int(f["wallet_age_days"]),
            float(f["avg_tx"]),
            float(f["recent_tx"]),
            float(f["tx_frequency"]),
            float(f["tx_per_min"]),
            float(f["tx_per_hour"]),
            float(f["tx_per_day"]),
            float(f["avg_time_between_tx_sec"]),
            int(time.time())
        ))

        conn.commit()
        print("[OK] FEATURES SAVED")

    except Exception as e:
        print("[ERROR] DB save error:", e)


# =============================
# LABELS (NEW ?)
# =============================
def get_label(wallet):
    try:
        if cursor is None:
            return None
        cursor.execute("""
            SELECT label, trusted
            FROM wallet_labels
            WHERE wallet=%s
        """, (wallet.lower(),))

        row = cursor.fetchone()

        if not row:
            return None

        return {
            "label": row[0],
            "trusted": bool(row[1])
        }

    except Exception as e:
        print("[ERROR] LABEL fetch error:", e)
        return None


def save_label(wallet, label, trusted):
    try:
        if cursor is None or conn is None:
            print("[WARN] DB disabled; skipping save_label")
            return
        cursor.execute("""
            INSERT INTO wallet_labels (wallet, label, trusted, updated_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (wallet)
            DO UPDATE SET
                label = EXCLUDED.label,
                trusted = EXCLUDED.trusted,
                updated_at = EXCLUDED.updated_at
        """, (
            wallet.lower(),
            label,
            trusted,
            int(time.time())
        ))

        conn.commit()
        print("?? LABEL SAVED")

    except Exception as e:
        print("[ERROR] LABEL save error:", e)
