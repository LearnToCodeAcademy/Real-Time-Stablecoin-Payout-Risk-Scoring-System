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

# [CRITICAL] Known stablecoin contract addresses - SKIP THESE
TOKEN_CONTRACTS = {
    "0xdAC17F958D2ee523a2206206994597C13D831ec7": "USDT",  # USDT contract
    "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48": "USDC",  # USDC contract
    "0x4Fabb145d64652a948d72533023f6E7A623C7C53": "BUSD",  # BUSD contract
    "0x6B175474E89094C44Da98b954EedeAC495271d0F": "DAI",   # DAI contract
    "0x8E870D67F660D95d5be2D627f142b3d3C9145e9D": "USDP",  # USDP contract
    "0x0000000000085d4780B73119b8B580991DEe8d52": "TUSD",  # TUSD contract
}



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

    # [CRITICAL] Check VERY HIGH model confidence FIRST (skip rules if model is very certain)

    if prob_poisoned >= 0.7:

        return "BLOCK", "Poisoned wallet (high confidence - address spoofing)"

    

    if prob_malicious >= 0.9:

        return "BLOCK", "Malicious wallet (very high confidence - phishing/scam)"

    

    # Then apply rule-based filters for lower confidence cases (defensive heuristics)

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



    # ? MEDIUM-HIGH POISONING

    if prob_poisoned >= 0.5:

        return "BLOCK", "Poisoned wallet (medium-high confidence)"



    # ? MEDIUM-HIGH MALICIOUS

    if prob_malicious >= 0.8:

        return "BLOCK", "Malicious wallet (high confidence)"



    elif prob_malicious >= 0.5:

        return "REVIEW", "Moderate malicious risk"



    return "ALLOW", "Low risk"



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

# FEATURE GEN - ALL 19 FEATURES

# =============================

def generate_features(transactions, wallet_address=None):
    """
    Generate all 19 features used by the trained models.
    Includes base features (8) + V3 poisoning features (4) + advanced heuristics (7).
    """
    rows = []
    senders = set()
    dust_count = 0
    similarity_hits = 0
    
    DUST_THRESHOLD = 0.001  # < 0.001 tokens = dust

    for tx in transactions:
        try:
            amount = int(tx["value"]) / (10 ** int(tx["tokenDecimal"]))
            if amount <= 0:
                continue
            
            timestamp = int(tx["timeStamp"])
            rows.append({"amount": amount, "timestamp": timestamp})
            
            # V3 Poisoning Detection
            if wallet_address:
                sender = tx.get("from", "")
                senders.add(sender)
                
                # Dust detection
                if amount < DUST_THRESHOLD:
                    dust_count += 1
                
                # Address similarity (spoofing pattern)
                if len(sender) >= 6 and len(wallet_address) >= 6:
                    if sender[:6] == wallet_address[:6] and sender[-4:] == wallet_address[-4:]:
                        similarity_hits += 1
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
            "avg_time_between_tx_sec": 0.0,
            "dust_tx_ratio": 0.0,
            "similarity_hits": 0,
            "new_sender_ratio": 0.0,
            "is_poisoned_pattern": 0,
            "tiny_tx_count": 0,
            "unique_receivers": 0,
            "avg_tx_value": 0.0,
            "window_days": 1,
            "repeat_small_to_count": 0,
            "no_meaningful_flow": 0,
            "short_time_window": 0
        }, True

    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
    df = df.sort_values("timestamp")

    wallet_age = max((df["timestamp"].max() - df["timestamp"].min()).days, 1)
    df["time_diff"] = df["timestamp"].diff().dt.total_seconds().fillna(0)

    total_seconds = max(
        (df["timestamp"].max() - df["timestamp"].min()).total_seconds(), 1
    )

    # V3 Poisoning Features
    total_txs = len(df)
    dust_ratio = dust_count / total_txs if total_txs > 0 else 0
    new_sender_ratio = len(senders) / total_txs if total_txs > 0 else 0
    
    # Poisoned pattern: dust + similarity + many senders
    is_poisoned = int(
        dust_ratio > 0.5 and similarity_hits > 0 and new_sender_ratio > 0.7
    )

    # Advanced heuristics (set reasonable defaults)
    tiny_tx_count = int((df["amount"] < 0.01).sum())
    unique_receivers = len(df)  # Approximate
    avg_tx_value = float(np.log1p(df["amount"].mean()))
    window_days = wallet_age
    repeat_small_to_count = 0  # Placeholder
    no_meaningful_flow = int(df["amount"].max() < 0.01)
    short_time_window = int(total_seconds < 86400)  # All txs within 1 day

    return {
        "wallet_age_days": int(wallet_age),
        "avg_tx": float(np.log1p(df["amount"].mean())),
        "recent_tx": float(np.log1p(df["amount"].iloc[-1])),
        "tx_frequency": float(len(df) / wallet_age),
        "tx_per_min": float(len(df) / (total_seconds / 60)),
        "tx_per_hour": float(len(df) / (total_seconds / 3600)),
        "tx_per_day": float(len(df) / (total_seconds / 86400)),
        "avg_time_between_tx_sec": float(df["time_diff"].mean()),
        "dust_tx_ratio": float(dust_ratio),
        "similarity_hits": int(similarity_hits),
        "new_sender_ratio": float(new_sender_ratio),
        "is_poisoned_pattern": int(is_poisoned),
        "tiny_tx_count": int(tiny_tx_count),
        "unique_receivers": int(unique_receivers),
        "avg_tx_value": float(avg_tx_value),
        "window_days": int(window_days),
        "repeat_small_to_count": int(repeat_small_to_count),
        "no_meaningful_flow": int(no_meaningful_flow),
        "short_time_window": int(short_time_window)
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

    # [CRITICAL] Validate address is not a known token contract
    address_lower = address.lower()
    for contract_addr, token_name in TOKEN_CONTRACTS.items():
        if address_lower == contract_addr.lower():
            print(f"\n[SKIP] Token Contract Address Detected")
            print(f"Address: {address}")
            print(f"Token: {token_name}")
            print(f"Reason: This is the {token_name} token contract, not a user wallet")
            print(f"Result: SKIP")
            print(f"? TOTAL TIME: {time.time() - total_start:.3f}s")
            return



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
        print(f"[ERROR] Could not detect token from {len(txs)} transactions")
        print(f"[ERROR] Supported tokens: {SUPPORTED_TOKENS}")
        print(f"[ERROR] Skipping wallet - cannot determine which model to use")
        return

    print(f"[OK] Using token model: {token}")



    # =============================

    # FEATURE GEN

    # =============================

    feat_start = time.time()

    features, low_data = generate_features(txs, address)

    print(f"? FEATURE TIME: {time.time() - feat_start:.3f}s")



    # =============================

    # SAVE TO DB

    # =============================

    try:

        save_features(address, token, features)

    except Exception as e:

        print(f"[WARN] DB save skipped: {e}")



    if low_data:
        print(f"[WARN] Insufficient valid {token} transaction data (< 3 transactions)")
        print(f"[WARN] Wallet may have very few confirmed token transfers")
        decision, reason = "REVIEW", f"Insufficient {token} transaction data (< 3 tx)"
        print(f"\n? RESULT (INSUFFICIENT DATA)")
        print(f"Wallet: {address}")
        print(f"Token: {token}")
        print(f"Decision: {decision}")
        print(f"Reason: {reason}")
        print("-" * 40)
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