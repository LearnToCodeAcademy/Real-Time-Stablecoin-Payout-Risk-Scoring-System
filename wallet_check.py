import requests
import pandas as pd
import pickle
import numpy as np
import time
from collections import Counter

# ✅ IMPORT DB FUNCTIONS (IMPORTANT)
from db import get_features, save_features

# =============================
# CONFIG
# =============================
API_KEY = "HVJKPIBXH53KSZFNTWI9RTEN6EXT9UXK7R"
BASE_URL = "https://api.etherscan.io/v2/api"

# =============================
# LOAD MODELS
# =============================
MODELS, SCALERS, FEATURE_COLS = {}, {}, {}

TOKENS = {
    "USDT": "models/usdt",
    "USDC": "models/usdc"
}

for token, path in TOKENS.items():
    try:
        MODELS[token] = pickle.load(open(f"{path}_model.pkl", "rb"))
        SCALERS[token] = pickle.load(open(f"{path}_scaler.pkl", "rb"))
        FEATURE_COLS[token] = pickle.load(open(f"{path}_features.pkl", "rb"))
    except:
        print(f"⚠️ Missing model for {token}")

# =============================
# FETCH TX
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

        res = requests.get(BASE_URL, params=params).json()
        result = res.get("result")

        return result if isinstance(result, list) else []
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
            if sym in ["USDT", "USDC"]:
                counts[sym] = counts.get(sym, 0) + 1

    return max(counts, key=counts.get) if counts else "USDT"

# =============================
# FEATURE GEN
# =============================
def generate_features(transactions):
    rows = []

    for tx in transactions:
        if not isinstance(tx, dict):
            continue

        try:
            amount = int(tx["value"]) / (10 ** int(tx["tokenDecimal"]))
            timestamp = int(tx["timeStamp"])
            rows.append({"amount": amount, "timestamp": timestamp})
        except:
            continue

    if len(rows) < 5:
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
        "wallet_age_days": wallet_age,
        "avg_tx": np.log1p(df["amount"].mean()),
        "recent_tx": np.log1p(df["amount"].iloc[-1]),
        "tx_frequency": len(df) / wallet_age,
        "tx_per_min": len(df) / (total_seconds / 60),
        "tx_per_hour": len(df) / (total_seconds / 3600),
        "tx_per_day": len(df) / (total_seconds / 86400),
        "avg_time_between_tx_sec": df["time_diff"].mean()
    }

# =============================
# NETWORK DETECTION
# =============================
def detect_network_patterns(address, txs):
    receivers, amounts, timestamps = [], [], []

    for tx in txs:
        if not isinstance(tx, dict):
            continue

        try:
            if tx.get("from") == address:
                receivers.append(tx.get("to"))

            amount = int(tx["value"]) / (10 ** int(tx["tokenDecimal"]))
            amounts.append(round(amount, 6))
            timestamps.append(int(tx["timeStamp"]))
        except:
            continue

    unique_receivers = len(set(receivers))
    receiver_counts = Counter(receivers)
    top_receiver_freq = max(receiver_counts.values()) if receiver_counts else 0

    amount_counts = Counter(amounts)
    top_amount_ratio = max(amount_counts.values()) / len(amounts) if amounts else 0

    timestamps.sort()
    diffs = np.diff(timestamps) if len(timestamps) > 1 else []
    fast_ratio = sum(d < 15 for d in diffs) / len(diffs) if len(diffs) > 0 else 0

    if top_receiver_freq > 20:
        return "BLOCK", "Clustered transfers"

    if top_amount_ratio > 0.6 and fast_ratio > 0.4:
        return "BLOCK", "Bot-like pattern"

    if unique_receivers > 25 and fast_ratio > 0.3:
        return "REVIEW", "Wide network pattern"

    return None, None

# =============================
# ML DECISION
# =============================
def classify_risk(prob, conf):
    if prob >= 0.8:
        return "BLOCK"
    elif prob >= 0.5 or conf < 0.2:
        return "REVIEW"
    return "ALLOW"

# =============================
# MAIN SCORER
# =============================
def score_wallet(address):
    txs = fetch_transactions(address)

    if not txs:
        print("⚠️ No transactions")
        return

    token = detect_token(txs)

    # 🔥 DB lookup
    features = get_features(address, token)

    if features:
        print("⚡ CACHE HIT (DB)")
    else:
        print("⚠️ Cache miss → computing...")
        features = generate_features(txs)

        if not features:
            print("⚠️ Not enough data")
            return

        save_features(address, token, features)

    # 🔥 Network detection
    net_decision, net_reason = detect_network_patterns(address, txs)

    if net_decision:
        print("\n🔥 NETWORK RESULT")
        print(f"Wallet: {address}")
        print(f"Decision: {net_decision}")
        print(f"Reason: {net_reason}")
        print("-" * 40)
        return

    # 🔥 ML scoring
    df_input = pd.DataFrame([features])
    scaled = SCALERS[token].transform(df_input[FEATURE_COLS[token]])

    prob = MODELS[token].predict_proba(scaled)[0][1]
    conf = abs(prob - 0.5) * 2

    print("\n🔥 ML RESULT")
    print(f"Wallet: {address}")
    print(f"Token: {token}")
    print(f"Risk: {prob:.4f}")
    print(f"Decision: {classify_risk(prob, conf)}")
    print(f"Confidence: {conf:.4f}")
    print("-" * 40)

# =============================
# RUN
# =============================
if __name__ == "__main__":
    print("\n🔥 Wallet Risk Scorer (CLEAN ARCH)")

    while True:
        w = input("\nWallet: ")

        if w.lower() == "exit":
            break

        if not w.startswith("0x"):
            print("❌ Invalid address")
            continue

        score_wallet(w)
        time.sleep(0.3)