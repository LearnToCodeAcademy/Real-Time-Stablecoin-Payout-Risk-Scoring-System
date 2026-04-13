import requests
import pandas as pd
import pickle
import numpy as np
import time

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
# DECISION ENGINE
# =============================
def classify_decision(prob, conf, features, low_data=False):
    if low_data:
        return "REVIEW", "Insufficient data"

    if features["wallet_age_days"] <= 1:
        return "REVIEW", "New wallet"

    if features["tx_per_day"] < 3:
        return "REVIEW", "Low activity"

    if conf < 0.3:
        return "REVIEW", "Low confidence"

    if prob >= 0.8:
        return "BLOCK", "High risk"

    elif prob >= 0.5:
        return "REVIEW", "Moderate risk"

    return "ALLOW", "Low risk"

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
            if sym in ["USDT", "USDC"]:
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
        return {
            "wallet_age_days": 1,
            "avg_tx": 0.0,
            "recent_tx": 0.0,
            "tx_frequency": 0.0,
            "tx_per_min": 0.0,
            "tx_per_hour": 0.0,
            "tx_per_day": 0.0,
            "avg_time_between_tx_sec": 0.0
        }, True

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
    }, False

# =============================
# MAIN SCORER
# =============================
def score_wallet(address):
    total_start = time.time()

    # =============================
    # DB CHECK
    # =============================
    db_start = time.time()

    for token in ["USDT", "USDC"]:
        features = get_features(address, token)

        if features and token in MODELS:
            db_time = time.time() - db_start
            print(f"⚡ CACHE HIT ({token}) → {db_time:.3f}s")

            df_input = pd.DataFrame([features])
            scaled = SCALERS[token].transform(df_input[FEATURE_COLS[token]])

            prob = MODELS[token].predict_proba(scaled)[0][1]
            conf = abs(prob - 0.5) * 2

            decision, reason = classify_decision(prob, conf, features)

            print("\n🔥 RESULT (DB)")
            print(f"Wallet: {address}")
            print(f"Token: {token}")
            print(f"Risk: {prob:.4f}")
            print(f"Decision: {decision}")
            print(f"Reason: {reason}")
            print("-" * 40)

            print(f"⏱ TOTAL TIME: {time.time() - total_start:.3f}s")
            return

    print(f"⚠️ DB MISS ({time.time() - db_start:.3f}s)")

    # =============================
    # API FETCH
    # =============================
    api_start = time.time()
    txs = fetch_transactions(address)
    print(f"🌐 API TIME: {time.time() - api_start:.3f}s")

    if not txs:
        print("No transactions")
        return

    token = detect_token(txs)

    if not token:
        print("⚠️ Token not detected → defaulting to USDT")
        token = "USDT"

    # =============================
    # FEATURE GEN
    # =============================
    feat_start = time.time()
    features, low_data = generate_features(txs)
    print(f"🧠 FEATURE TIME: {time.time() - feat_start:.3f}s")

    # =============================
    # SAVE TO DB
    # =============================
    try:
        save_features(address, token, features)
    except Exception as e:
        print(f"⚠️ DB save skipped: {e}")

    if low_data:
        print("Low data → REVIEW")
        print(f"⏱ TOTAL TIME: {time.time() - total_start:.3f}s")
        return

    if token not in MODELS:
        print(f"⚠️ No model for {token} → REVIEW")
        print(f"⏱ TOTAL TIME: {time.time() - total_start:.3f}s")
        return

    # =============================
    # ML INFERENCE
    # =============================
    df_input = pd.DataFrame([features])
    scaled = SCALERS[token].transform(df_input[FEATURE_COLS[token]])

    prob = MODELS[token].predict_proba(scaled)[0][1]
    conf = abs(prob - 0.5) * 2

    decision, reason = classify_decision(prob, conf, features)

    print("\n🔥 RESULT")
    print(f"Wallet: {address}")
    print(f"Token: {token}")
    print(f"Risk: {prob:.4f}")
    print(f"Decision: {decision}")
    print(f"Reason: {reason}")
    print("-" * 40)

    print(f"⏱ TOTAL TIME: {time.time() - total_start:.3f}s")

# =============================
# RUN
# =============================
if __name__ == "__main__":
    print("🔥 FINAL SYSTEM")

    while True:
        w = input("\nWallet: ")

        if w.lower() == "exit":
            break

        if not w.startswith("0x"):
            print("❌ Invalid address")
            continue

        score_wallet(w)
        time.sleep(0.3)