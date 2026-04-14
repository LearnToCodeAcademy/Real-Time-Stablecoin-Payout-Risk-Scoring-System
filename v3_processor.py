import requests
import pandas as pd
import numpy as np
import time

API_KEY = "YOUR_API_KEY"
BASE_URL = "https://api.etherscan.io/v2/api"

INPUT_PATH = "datasets/v3_raw.csv"
OUTPUT_PATH = "datasets/usdt_labeled_v3.csv"

# =============================
# FETCH TRANSACTIONS
# =============================
def fetch_transactions(wallet):
    try:
        res = requests.get(BASE_URL, params={
            "chainid": 1,
            "module": "account",
            "action": "tokentx",
            "address": wallet,
            "offset": 100,
            "sort": "desc",
            "apikey": API_KEY
        }).json()

        result = res.get("result")
        return result if isinstance(result, list) else []
    except:
        return []

# =============================
# BASE FEATURES (V0 STYLE)
# =============================
def compute_base_features(txs):
    rows = []

    for tx in txs:
        try:
            amount = int(tx["value"]) / (10 ** int(tx["tokenDecimal"]))
            timestamp = int(tx["timeStamp"])
            rows.append({"amount": amount, "timestamp": timestamp})
        except:
            continue

    if len(rows) < 3:
        return None

    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
    df = df.sort_values("timestamp")

    wallet_age = max((df["timestamp"].max() - df["timestamp"].min()).days, 1)

    df["time_diff"] = df["timestamp"].diff().dt.total_seconds().fillna(0)

    total_seconds = max(
        (df["timestamp"].max() - df["timestamp"].min()).total_seconds(), 1
    )

    return {
        "wallet_age_days": int(wallet_age),
        "avg_tx": float(np.log1p(df["amount"].mean())),
        "recent_tx": float(np.log1p(df["amount"].iloc[-1])),
        "tx_frequency": float(len(df) / wallet_age),
        "tx_per_min": float(len(df) / (total_seconds / 60)),
        "tx_per_hour": float(len(df) / (total_seconds / 3600)),
        "tx_per_day": float(len(df) / (total_seconds / 86400)),
        "avg_time_between_tx_sec": float(df["time_diff"].mean())
    }

# =============================
# MAIN
# =============================
df = pd.read_csv(INPUT_PATH)

# 🔥 keep only poisoned
df = df[df["label"] == 2]

print(f"🔥 Poisoned wallets to process: {len(df)}")

rows = []

for i, row in df.iterrows():
    wallet = row["wallet"]

    print(f"🔍 [{i+1}/{len(df)}] {wallet}")

    txs = fetch_transactions(wallet)

    if not txs:
        continue

    base = compute_base_features(txs)

    if not base:
        continue

    rows.append({
        "wallet": wallet,
        **base,
        "dust_tx_ratio": row["dust_tx_ratio"],
        "similarity_hits": row["similarity_hits"],
        "new_sender_ratio": row["new_sender_ratio"],
        "is_poisoned_pattern": row["is_poisoned_pattern"],
        "label": 2
    })

    time.sleep(0.2)

# =============================
# SAVE
# =============================
df_final = pd.DataFrame(rows)

# 🔥 IMPORTANT FIX
df_final = df_final.drop_duplicates(subset=["wallet"])

if df_final.empty:
    print("⚠️ No valid V3 samples found")

df_final.to_csv(OUTPUT_PATH, index=False)

print(f"\n✅ V3 READY → {OUTPUT_PATH} ({len(df_final)} rows)")