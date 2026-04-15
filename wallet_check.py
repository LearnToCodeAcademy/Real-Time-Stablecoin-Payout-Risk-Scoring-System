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

SUPPORTED_TOKENS = ["USDT", "USDC", "BUSD", "DAI", "USDP", "TUSD"]  # Only trained tokens have models

# [EXPANSION] All supported tokens for detection/reporting (54 tokens)
# TRAINED=6 (marked with *), WATCHONLY=48 for detection-only mode
ALL_TOKENS = {
    # ===== STABLECOINS: Trained (6) + Watch-Only (18) =====
    "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",  # * Tether (TRAINED)
    "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",  # * USD Coin (TRAINED)
    "DAI":  "0x6B175474E89094C44Da98b954EedeAC495271d0F",  # * DAI (TRAINED)
    "BUSD": "0x4Fabb145d64652a948d72533023f6E7A623C7C53",  # * Binance USD (TRAINED)
    "USDP": "0x8E870D67F660D95d5be2D627f142b3d3C9145e9D",  # * Paxos USD (TRAINED)
    "TUSD": "0x0000000000085d4780B73119b8B580991DEe8d52",  # * True USD (TRAINED)
    "FRAX": "0x853d955aCEf822Db058eb8505911ED77F175b999",  # Frax
    "USDX": "0xEB269732ab75A6fD61Ea60b06Fe994cD32a83549",  # Usdx
    "GUSD": "0x056Fd409E1d7a124BD7017459dFEa2F387b6d5Cd",  # Gemini USD
    "LUSD": "0x5f98805A4E8f28Fb3fBEa8E3302F36A6c4089d5d",  # Liquity USD
    "MIM":  "0x99D8a9C45b2ecA8864373A26D1459e3Dff1e17F3",  # Magic Internet Money
    "USDD": "0x0C10bF8FcB7BEe7545050DC9fBa090257BF378C1",  # USDD (Tron Stablecoin)
    "EURS": "0xdB25f211AB05b1c97D595fc342622f313F7ba4A8",  # EURS (Stasis Euro)
    "DOLA": "0x865377367054516e404113458AfE5F5B352318De",  # dForce USD (Dola)
    "GOHM": "0x0ab87046fBb341D058F17CBC4c1133F25a20a52f",  # Governance Ohm
    "USDCE":"0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174", # USD Coin (Polygon)
    "ALUSD":"0xBC6DA0FE9aD5f3b0d56f3302D25CD78a3891AB28", # Alchemix USD
    "cUSDT":"0xf650C3d88D12dB855b8bf7D11Be6C55A660128C0",  # cUSDT (Compound)
    
    # ===== DeFi TOKENS: Watch-Only (12) =====
    "AAVE": "0x7Fc66500c84A76Ad7e9c93437E434122A1f9AcDd",  # Aave
    "COMP": "0xc00e94cb662c3520282e6f5717214200A2f38f2D",  # Compound
    "SNX":  "0xC011a73ee3C7781c43Ef8664CaCBA5Bfb4B5C91d",  # Synthetix
    "UNI":  "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",  # Uniswap
    "LINK": "0x514910771AF9ca656af840dff83E8264EcF986CA",  # Chainlink
    "SUSHI":"0x6B3595068778DD592e39A122f4f5a5cF09C90fE2",  # SushiSwap
    "CRV":  "0xD533a949740bb3306d119CC777fa900bA034cd52",  # Curve
    "1INCH":"0x111111111117dC0aa78b770fA6A738034120C302",  # 1Inch
    "YFI":  "0x0bc529c00C6401aEA6830052eCs38aEA4104B4De",  # yearn.finance
    "MKR":  "0x9f8F72aA9304c8B593d555F12eF6589cC3A579A2",  # Maker
    "BAL":  "0xba100000625a3754423f8282f6b5d4d66c75da24",  # Balancer
    "AURA": "0xC0c293ce456fF0ED870ADd98bc6A6B9DD3B2E76d",  # Aura
    
    # ===== ETH/L2 TOKENS: Watch-Only (9) =====
    "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # Wrapped Ether
    "MATIC": "0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0",  # Polygon (Matic)
    "LDO":  "0x5A98FcBEA516Cf06857215779Fd812CA3beF1B32",  # Lido
    "ARB":  "0xB50721BCF8d664c30412Cfbc6cf7a15145234ad1",  # Arbitrum
    "OP":   "0x4200000000000000000000000000000000000042",  # Optimism
    "GMX":  "0xfc5A1A6EB076a2C7aD06eD22C90d3E710233C904",  # GMX
    "SOL":  "0xD31a59c85aE9D8edEFeC411D448f90541670C06d",  # Wrapped SOL
    "MANTLE":"0x78c1b0C915c4FAA5FffA6CEB6a922F73389E405B",  # Mantle
    "LINEA":"0x0a6ce4409d3a4f56a928ac6302e7f2e4f19a8db8",  # Linea
    
    # ===== WRAPPED TOKENS: Watch-Only (8) =====
    "WBTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",  # Wrapped Bitcoin
    "cBTC": "0x7e7E112A68d8D2E221E11047a72fFC1d8EF3467f",  # cBTC
    "stETH":"0xae7ab96520DE3A18E5e111B5eaAb095312D7fE84",  # Lido staked ETH
    "rswETH":"0xA1290d69c65A6Fe4DF752f95823fae25cB99e5A7",  # Restake Staked ETH
    "CBETH":"0xBe9895146f7AF43049ca1c1AE358B0541ea49704",  # Coinbase staked ETH
    "LST":  "0x1f32b1c2345538c0c6f582fcB022739c4A194Ebb",  # Liquid Stake Token
    "cbRES":"0x99cbdb6Ee0E6472Cb3c177C5D8d8fC1d9Fe6E6Ee",  # Coinbase Reward ETH
    "swETH":"0xf951E335afb289fa71f856386d3D3E74Ffb50Ea3",  # Swell staked ETH
    
    # ===== MEME/OTHER TOKENS: Watch-Only (7) =====
    "DOGE": "0xBA2aE424d960c26247Dd6c32edC70B295c744C43",  # Dogecoin (wrapped)
    "SHIB": "0x95aD61b0a150d79219dCF64E1E6Cc01f0B64C4cE",  # Shiba Inu
    "PEPE": "0x6982508145454Ce894aaEc87E1Ac8D4e98E9DB4d",  # Pepe
    "FLOKI":"0xcf0C122c6b5E2485eb96245300256c8F63F20971",  # Floki
    "BONK": "0xB0B195aEFA3650A6908f15CdAc7D92F90912C595",  # Bonk (wrapped)
    "WLD":  "0x163f8C2467924be0ae7E9ACaD2d45CE03d395278",  # World Coin
    "SAFE": "0x5aFb0a56a78D6FA7d4f7850B0DF9e11AD015d211",  # Safe (Gnosis)
}

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
# LAZY MODEL LOADING (on-demand)
# =============================
# Models are loaded only when needed to avoid startup delays and KeyboardInterrupt issues

MODELS, SCALERS, FEATURE_COLS = {}, {}, {}


def load_model_for_token(token):
    """
    Lazy load model for a specific token.
    Called only when scoring is actually needed.
    """
    if token in MODELS:
        return  # Already loaded
    
    if token not in SUPPORTED_TOKENS:
        raise ValueError(f"No model available for token {token}")
    
    prefix = os.path.join(MODEL_DIR, token.lower())
    model_path = f"{prefix}_model.pkl"
    scaler_path = f"{prefix}_scaler.pkl"
    features_path = f"{prefix}_features.pkl"
    
    if os.path.exists(model_path) and os.path.exists(scaler_path) and os.path.exists(features_path):
        try:
            MODELS[token] = pickle.load(open(model_path, "rb"))
            SCALERS[token] = pickle.load(open(scaler_path, "rb"))
            FEATURE_COLS[token] = pickle.load(open(features_path, "rb"))
            print(f"[OK] Loaded model for {token}")
        except Exception as e:
            print(f"[WARN] Failed to load {token} model: {e}")
            raise
    else:
        raise FileNotFoundError(f"Model files missing for {token}")


# Pre-load at startup for diagnostics (optional, catches issues early)
try:
    for token in SUPPORTED_TOKENS:
        prefix = os.path.join(MODEL_DIR, token.lower())
        model_path = f"{prefix}_model.pkl"
        if os.path.exists(model_path):
            load_model_for_token(token)
except Exception as e:
    print(f"[WARN] Model pre-load issue: {e} (will attempt lazy load on use)")



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
    """
    Detect token from transaction list.
    - Checks top 20 transactions
    - Reports which tokens found (both TRAINED and WATCHONLY)
    - Returns token if in TRAINED_TOKENS list, None otherwise
    """
    counts = {}
    
    # Check top 20 most recent transactions
    for tx in transactions[:20]:
        if isinstance(tx, dict):
            sym = tx.get("tokenSymbol")
            if isinstance(sym, str):
                sym = sym.upper().strip()
                # Check against expanded tokens list
                if sym in ALL_TOKENS:
                    counts[sym] = counts.get(sym, 0) + 1
    
    if not counts:
        print("[WARN] No recognized tokens found in transaction history")
        return None
    
    # Find most common token
    detected_token = max(counts, key=counts.get)
    count = counts[detected_token]
    
    # Check if it's a trained token
    if detected_token in SUPPORTED_TOKENS:
        print(f"[OK] Found TRAINED token: {detected_token} (count: {count}) - Scoring enabled")
        return detected_token
    else:
        # It's a watchonly token - report but don't score
        other_tokens = [f"{t} ({counts[t]})" for t in sorted(counts.keys()) if t != detected_token]
        other_str = f" | Other detected: {', '.join(other_tokens)}" if other_tokens else ""
        print(f"[WARN] Detected token: {detected_token} (count: {count}) - UNSUPPORTED (no model trained){other_str}")
        print(f"[SKIP] {detected_token} wallet scoring disabled - model not available")
        return None



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

        # Check if model is available (SUPPORTED_TOKENS, not MODELS dict which uses lazy loading)
        if features is not None and token in SUPPORTED_TOKENS:

            db_time = time.time() - db_start

            print(f"? CACHE HIT ({token}) ? {db_time:.3f}s")



            df_input = align_features_for_token(token, features)

            try:
                # Ensure model is loaded
                load_model_for_token(token)
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
        print(f"[ERROR] Scoring skipped - no supported token model available")
        print(f"? TOTAL TIME: {time.time() - total_start:.3f}s")
        return

    print(f"[OK] Proceeding with {token} model scoring...")



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



    if token not in SUPPORTED_TOKENS:

        decision, reason = "REVIEW", f"Model not available for {token}"

        print(f"[WARN] No model for {token} - token not in SUPPORTED_TOKENS")

        print(f"Decision: {decision}")

        print(f"Reason: {reason}")

        print(f"? TOTAL TIME: {time.time() - total_start:.3f}s")

        return

    # Ensure model is loaded before inference
    try:
        load_model_for_token(token)
    except Exception as e:
        print(f"[ERROR] Failed to load model for {token}: {e}")
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