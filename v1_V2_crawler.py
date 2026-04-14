
import requests
import pandas as pd
import numpy as np
import time

# =============================
# CONFIG
# =============================
API_KEY = "DX83H5UW7Z4R4XBYAAMB3QY1ZNHWM7KUHX"
BASE_URL = "https://api.etherscan.io/v2/api"

# 🔥 LOAD WALLETS FROM CSV
CSV_PATH = "wallet_pool.csv"

TOKENS = ["USDT", "USDC"]

# =============================
# LOAD WALLETS
# =============================
def load_wallets(csv_path):
    try:
        df = pd.read_csv(csv_path)

        if "wallet" not in df.columns:
            raise Exception("❌ CSV must contain 'wallet' column")

        wallets = df["wallet"].dropna().unique().tolist()

        print(f"✅ Loaded {len(wallets)} wallets from CSV")
        return wallets

    except Exception as e:
        print("❌ Failed to load CSV:", e)
        return []

# =============================
# FETCH
# =============================
def fetch_transactions(address):
    try:
        params = {
            "chainid": 1,
            "module": "account",
            "action": "tokentx",
            "address": address,
            "offset": 100,
            "sort": "desc",
            "apikey": API_KEY
        }

        return requests.get(BASE_URL, params=params).json().get("result", [])
    except:
        return []

# =============================
# TOKEN DETECT
# =============================
def detect_token(transactions):
    counts = {}

    for tx in transactions:
        if isinstance(tx, dict):
            sym = tx.get("tokenSymbol")
            if sym in TOKENS:
                counts[sym] = counts.get(sym, 0) + 1

    return max(counts, key=counts.get) if counts else None

# =============================
# FEATURE GEN
# =============================
def generate_features(transactions):
    rows = []

    for tx in transactions:
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
        "avg_tx": float(np.mean(df["amount"])),
        "recent_tx": float(df["amount"].iloc[-1]),
        "tx_frequency": float(len(df) / wallet_age),
        "tx_per_min": float(len(df) / (total_seconds / 60)),
        "tx_per_hour": float(len(df) / (total_seconds / 3600)),
        "tx_per_day": float(len(df) / (total_seconds / 86400)),
        "avg_time_between_tx_sec": float(df["time_diff"].mean())
    }

# =============================
# RULE FLAGS
# =============================
def compute_rules(features):
    is_high_freq = features["tx_per_day"] > 50
    is_low_value = features["avg_tx"] < 1
    is_new_wallet = features["wallet_age_days"] <= 7

    risk_score = 0

    if is_high_freq:
        risk_score += 0.4
    if is_low_value:
        risk_score += 0.3
    if is_new_wallet:
        risk_score += 0.3

    return is_high_freq, is_low_value, is_new_wallet, min(risk_score, 1.0)

# =============================
# MAIN
# =============================
results = []

WALLETS = load_wallets(CSV_PATH)

for wallet in WALLETS:
    print(f"\n🔍 Processing: {wallet}")

    txs = fetch_transactions(wallet)

    if not txs:
        print("❌ No transactions")
        continue

    token = detect_token(txs)

    if not token:
        print("❌ No supported token")
        continue

    features = generate_features(txs)

    if not features:
        print("❌ Not enough data")
        continue

    is_high_freq, is_low_value, is_new_wallet, risk_score = compute_rules(features)

    row = {
        "wallet": wallet,
        "token": token,
        **features,
        "is_high_freq": is_high_freq,
        "is_low_value": is_low_value,
        "is_new_wallet": is_new_wallet,
        "risk_score_rule": risk_score,
        "label": None
    }

    results.append(row)

    time.sleep(0.3)

# =============================
# OUTPUT
# =============================
df = pd.DataFrame(results)

print("\n📊 AL RESULT:")
print(df)

df.to_csv("51k_one_checker_output.csv", index=False)
print("\n✅ Saved to one_checker_output.csv")
