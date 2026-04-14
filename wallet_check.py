import os
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
BASE_URL = "https://api.etherscan.io/api"
MODEL_DIR = "models"
SUPPORTED_TOKENS = ["USDT", "USDC", "BUSD", "DAI", "USDP", "TUSD"]

# =============================
# LOAD MODELS
# =============================
MODELS, SCALERS, FEATURE_COLS = {}, {}, {}

for token in SUPPORTED_TOKENS:
    prefix = os.path.join(MODEL_DIR, token.lower())
    model_path = f"{prefix}_model.pkl"
    scaler_path = f"{prefix}_scaler.pkl"
    features_path = f"{prefix}_features.pkl"

    if os.path.exists(model_path) and os.path.exists(scaler_path) and os.path.exists(features_path):
        try:
            MODELS[token] = pickle.load(open(model_path, "rb"))
            SCALERS[token] = pickle.load(open(scaler_path, "rb"))
            FEATURE_COLS[token] = pickle.load(open(features_path, "rb"))
        except Exception as e:
            print(f"[WARN] Failed to load {token} model: {e}")
    else:
        print(f"[WARN] Missing files for {token} model; expected {model_path}, {scaler_path}, {features_path}")

if MODELS:
    print(f"[OK] Loaded token models: {', '.join(sorted(MODELS.keys()))}")
else:
    print("[WARN] No token models loaded. Wallet scoring will require model files in models/*_model.pkl.")

# =============================
# RULE-BASED HEURISTICS (DEFENSIVE)
# =============================
# These rules catch high-risk patterns even if ML confidence is low
# Applied BEFORE and AFTER ML classification for extra safety

def apply_rule_based_filters(features, prob_malicious, prob_poisoned):
    """
    Apply deterministic rule-based checks to catch known attack patterns.
    Returns: (override_decision, override_confidence, rule_fired)
    """
    
    # Rule 1: NEW WALLET (< 7 days) with ANY suspicious activity
    if features.get("wallet_age_days", 100) <= 7:
        if prob_malicious > 0.3 or prob_poisoned > 0.2:
            return "REVIEW", 0.9, "new_wallet_suspicious"
    
    # Rule 2: ULTRA-HIGH FREQUENCY + LOW VALUE (classic spam)
    if features.get("tx_per_day", 0) > 50 and features.get("avg_tx", 1000) < 1.0:
        return "BLOCK", 0.95, "spam_pattern_high_freq_low_value"
    
    # Rule 3: NO MEANINGFUL ACTIVITY (all dust/zero transactions)
    if features.get("avg_tx", 1000) < 0.001 and features.get("tx_frequency", 0) > 10:
        return "BLOCK", 0.85, "no_meaningful_activity"
    
    # Rule 4: INSTANT TRANSACTIONS (avg time between tx < 10 seconds = bots)
    if features.get("avg_time_between_tx_sec", 100000) < 10 and features.get("tx_frequency", 0) > 5:
        return "BLOCK", 0.80, "bot_activity_instant_txs"
    
    # Rule 5: RECENT SPIKE IN ACTIVITY (dormant wallet suddenly active)
    if (features.get("recent_tx", 0) > features.get("avg_tx", 1) * 10 and 
        features.get("wallet_age_days", 1) > 365 and
        features.get("tx_per_min", 0) > 0.1):
        return "REVIEW", 0.75, "unusual_spike_old_wallet"
    
    # Rule 6: ABNORMAL HOUR ACTIVITY (> 20 txs/hour = unusual)
    if features.get("tx_per_hour", 0) > 20:
        return "REVIEW", 0.70, "abnormal_tx_rate_hourly"
    
    return None, None, None


# =============================
# DECISION ENGINE (3-CLASS) + RULES
# =============================
def classify_decision(prob_malicious, prob_poisoned, conf, features, low_data=False):
    # First, apply rule-based filters (defensive blocking)
    rule_decision, rule_conf, rule_name = apply_rule_based_filters(features, prob_malicious, prob_poisoned)
    if rule_decision:
        return rule_decision, f"{rule_name} (rule-based check)"
    
    if low_data:
        return "REVIEW", "Insufficient data"

    if features["wallet_age_days"] <= 1:
        return "REVIEW", "New wallet"

    if features["tx_per_day"] < 3:
        return "REVIEW", "Low activity"

    if conf < 0.3:
        return "REVIEW", "Low confidence"

    # ? POISONING IS HIGHEST PRIORITY
    if prob_poisoned >= 0.5:
        return "BLOCK", "Poisoned wallet (address spoofing)"

    # ? THEN MALICIOUS
    if prob_malicious >= 0.8:
        return "BLOCK", "High malicious risk"

    elif prob_malicious >= 0.5:
        return "REVIEW", "Moderate malicious risk"

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
    supported = list(MODELS.keys()) if MODELS else SUPPORTED_TOKENS

    for tx in transactions:
        if isinstance(tx, dict):
            sym = tx.get("tokenSymbol")
            if isinstance(sym, str):
                sym = sym.upper().strip()
            if sym in supported:
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
            if amount <= 0:
                continue
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
# ML PROBABILITY HELPERS
# =============================
def get_token_probabilities(model, scaled):
    probs = model.predict_proba(scaled)[0]
    class_index = {cls: idx for idx, cls in enumerate(model.classes_)}

    prob_normal = float(probs[class_index[0]]) if 0 in class_index else 0.0
    prob_malicious = float(probs[class_index[1]]) if 1 in class_index else 0.0
    prob_poisoned = float(probs[class_index[2]]) if 2 in class_index else 0.0

    return prob_normal, prob_malicious, prob_poisoned


def align_features_for_token(token, features):
    """Return input DataFrame with expected model columns for the given token."""
    feature_cols = FEATURE_COLS.get(token)
    df_input = pd.DataFrame([features])

    if feature_cols is None:
        return df_input

    for col in feature_cols:
        if col not in df_input.columns:
            df_input[col] = 0

    return df_input[feature_cols]


# =============================
# MAIN SCORER
# =============================
def score_wallet(address):
    total_start = time.time()

    # =============================
    # DB CHECK
    # =============================
    db_start = time.time()

    for token in MODELS:
        features = get_features(address, token)

        if features is not None and token in MODELS:
            db_time = time.time() - db_start
            print(f"? CACHE HIT ({token}) ? {db_time:.3f}s")

            df_input = align_features_for_token(token, features)
            try:
                scaled = SCALERS[token].transform(df_input)
            except Exception as e:
                print(f"[WARN] Cached inference failed for {token}: {e}. Skipping.")
                continue

            prob_normal, prob_malicious, prob_poisoned = get_token_probabilities(MODELS[token], scaled)
            risk_prob = max(prob_malicious, prob_poisoned)
            conf = abs(risk_prob - 0.5) * 2

            decision, reason = classify_decision(prob_malicious, prob_poisoned, conf, features)

            print("\n? RESULT (DB)")
            print(f"Wallet: {address}")
            print(f"Token: {token}")
            print(f"Normal: {prob_normal:.4f}")
            print(f"Malicious: {prob_malicious:.4f}")
            print(f"Poisoned: {prob_poisoned:.4f}")
            print(f"Decision: {decision}")
            print(f"Reason: {reason}")
            print("-" * 40)

            print(f"? TOTAL TIME: {time.time() - total_start:.3f}s")
            return

    print(f"[WARN] DB MISS ({time.time() - db_start:.3f}s)")

    # =============================
    # API FETCH
    # =============================
    api_start = time.time()
    txs = fetch_transactions(address)
    print(f"? API TIME: {time.time() - api_start:.3f}s")

    if not txs:
        print("No transactions")
        return

    token = detect_token(txs)

    if not token:
        print("[WARN] Token not detected ? defaulting to USDT")
        token = "USDT"

    print(f"MOST USE TOKEN: {token}")

    # =============================
    # FEATURE GEN
    # =============================
    feat_start = time.time()
    features, low_data = generate_features(txs)
    print(f"? FEATURE TIME: {time.time() - feat_start:.3f}s")

    # =============================
    # SAVE TO DB
    # =============================
    try:
        save_features(address, token, features)
    except Exception as e:
        print(f"[WARN] DB save skipped: {e}")

    if low_data:
        decision, reason = "REVIEW", "Insufficient transaction data"
        print("Low data ? REVIEW")
        print(f"Decision: {decision}")
        print(f"Reason: {reason}")
        print(f"? TOTAL TIME: {time.time() - total_start:.3f}s")
        return

    if token not in MODELS:
        decision, reason = "REVIEW", "No model available for detected token"
        print(f"[WARN] No model for {token} ? REVIEW")
        print(f"Decision: {decision}")
        print(f"Reason: {reason}")
        print(f"? TOTAL TIME: {time.time() - total_start:.3f}s")
        return

    # =============================
    # ML INFERENCE (3-CLASS)
    # =============================
    df_input = align_features_for_token(token, features)
    try:
        scaled = SCALERS[token].transform(df_input)
    except Exception as e:
        print(f"[WARN] Model inference failed for {token}: {e}. REVIEW")
        print(f"? TOTAL TIME: {time.time() - total_start:.3f}s")
        return

    prob_normal, prob_malicious, prob_poisoned = get_token_probabilities(MODELS[token], scaled)
    risk_prob = max(prob_malicious, prob_poisoned)
    conf = abs(risk_prob - 0.5) * 2

    decision, reason = classify_decision(prob_malicious, prob_poisoned, conf, features)

    print("\n? RESULT")
    print(f"Wallet: {address}")
    print(f"Token: {token}")
    print(f"Normal: {prob_normal:.4f}")
    print(f"Malicious: {prob_malicious:.4f}")
    print(f"Poisoned: {prob_poisoned:.4f}")
    print(f"Decision: {decision}")
    print(f"Reason: {reason}")
    print("-" * 40)

    print(f"? TOTAL TIME: {time.time() - total_start:.3f}s")

# =============================
# RUN
# =============================
if __name__ == "__main__":
    print("? FINAL SYSTEM")

    while True:
        w = input("\nWallet: ")

        if w.lower() == "exit":
            break

        if not w.startswith("0x"):
            print("[ERROR] Invalid address")
            continue

        score_wallet(w)
        time.sleep(0.3)