import psycopg2
import time
import os
from dotenv import load_dotenv
from pathlib import Path

# =============================
# LOAD ENV (FORCE PATH SAFE)
# =============================
BASE_DIR = Path(__file__).resolve().parent
env_path = BASE_DIR / ".env"

load_dotenv(dotenv_path=env_path)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise Exception("❌ DATABASE_URL not found. Check your .env file location.")

# =============================
# CONNECT DB
# =============================
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

print("✅ DB CONNECTED")

# =============================
# GET FEATURES
# =============================
def get_features(wallet, token):
    try:
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
        print("❌ DB fetch error:", e)
        return None


# =============================
# SAVE FEATURES (FIXED)
# =============================
def save_features(wallet, token, f):
    try:
        # 🔥 CRITICAL FIX: convert all values to Python types
        f = {
            "wallet_age_days": int(f["wallet_age_days"]),
            "avg_tx": float(f["avg_tx"]),
            "recent_tx": float(f["recent_tx"]),
            "tx_frequency": float(f["tx_frequency"]),
            "tx_per_min": float(f["tx_per_min"]),
            "tx_per_hour": float(f["tx_per_hour"]),
            "tx_per_day": float(f["tx_per_day"]),
            "avg_time_between_tx_sec": float(f["avg_time_between_tx_sec"])
        }

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
            f["wallet_age_days"],
            f["avg_tx"],
            f["recent_tx"],
            f["tx_frequency"],
            f["tx_per_min"],
            f["tx_per_hour"],
            f["tx_per_day"],
            f["avg_time_between_tx_sec"],
            int(time.time())
        ))

        conn.commit()
        print("✅ SAVED TO DB")

    except Exception as e:
        print("❌ DB save error:", e)