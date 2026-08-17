import os

import requests

import pandas as pd

import pickle

import numpy as np

import time


from db import get_features, save_features

# 🧠 GRAPH ENGINE - Network Intelligence
try:
    from graph_engine import TransactionGraph
except ImportError:
    TransactionGraph = None

# 🧠 INTERPRETABILITY - SHAP Explainability
try:
    import shap
    HAS_SHAP = True
except ImportError:
    HAS_SHAP = False



# =============================

# CONFIG

# =============================

API_KEY = os.getenv("ETHERSCAN_API_KEY") or os.getenv("ETHERSCAN_API_KEY_V0", "")

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
# TOKEN-SPECIFIC SCORING RULES
# =============================
# Different tokens = different attack patterns = different detection logic
TOKEN_SCORING_RULES = {
    "USDT": {
        "description": "Tether - Institutional stablecoin",
        "risk_profile": "HIGH_VALUE_TARGETS",
        "malicious_threshold": 0.88,  # Stripe institutional accounts
        "poisoned_threshold": 0.75,   # Credential theft patterns
        "rule_checks": ["large_tx_spike", "unusual_institution_pattern", "cex_withdrawal_spam"],
        "anomaly_window_hours": 24,
    },
    "USDC": {
        "description": "Circle USD Coin",
        "risk_profile": "RETAIL_PHISHING",
        "malicious_threshold": 0.85,
        "poisoned_threshold": 0.72,
        "rule_checks": ["social_engineering", "fake_contract_interaction", "high_frequency_spam"],
        "anomaly_window_hours": 6,
    },
    "DAI": {
        "description": "MakerDAO Stablecoin",
        "risk_profile": "DEFI_EXPLOITS",
        "malicious_threshold": 0.82,
        "poisoned_threshold": 0.70,
        "rule_checks": ["flash_loan_patterns", "collateral_manipulation", "governance_attack_setup"],
        "anomaly_window_hours": 1,
    },
    "BUSD": {
        "description": "Binance USD",
        "risk_profile": "EXCHANGE_MANIPULATION",
        "malicious_threshold": 0.86,
        "poisoned_threshold": 0.73,
        "rule_checks": ["exchange_arb_wash", "institutional_spoofing", "cex_margin_attack"],
        "anomaly_window_hours": 12,
    },
    "USDP": {
        "description": "Paxos USD",
        "risk_profile": "REGULATORY_EVASION",
        "malicious_threshold": 0.83,
        "poisoned_threshold": 0.71,
        "rule_checks": ["aml_bypass_pattern", "sanctioned_wallet_routing", "privacy_mixer_usage"],
        "anomaly_window_hours": 48,
    },
    "TUSD": {
        "description": "True USD",
        "risk_profile": "BRIDGE_EXPLOITS",
        "malicious_threshold": 0.84,
        "poisoned_threshold": 0.72,
        "rule_checks": ["bridge_exploit_signature", "redemption_fraud", "cross_chain_manipulation"],
        "anomaly_window_hours": 36,
    },
}

# =============================
# TOKEN TYPE CLASSIFICATION
# =============================
# Critical: Different token types have COMPLETELY DIFFERENT attacker profiles
TOKEN_TYPE_CLASSIFICATION = {
    # Stablecoins (18): Attackers use phishing, credentials, institutional hacks
    "USDT": "stablecoin", "USDC": "stablecoin", "BUSD": "stablecoin", "DAI": "stablecoin",
    "USDP": "stablecoin", "TUSD": "stablecoin", "FRAX": "stablecoin", "USDX": "stablecoin",
    "GUSD": "stablecoin", "LUSD": "stablecoin", "MIM": "stablecoin", "USDD": "stablecoin",
    "EURS": "stablecoin", "DOLA": "stablecoin", "GOHM": "stablecoin", "USDCE": "stablecoin",
    "ALUSD": "stablecoin", "cUSDT": "stablecoin",
    
    # DeFi Tokens (12): Attackers exploit contracts, governance, flash loans
    "AAVE": "defi", "COMP": "defi", "SNX": "defi", "UNI": "defi",
    "LINK": "defi", "SUSHI": "defi", "CRV": "defi", "1INCH": "defi",
    "YFI": "defi", "MKR": "defi", "BAL": "defi", "AURA": "defi",
    
    # Native/L2 (9): Layer 2 protocols, ETH derivative attacks
    "WETH": "native", "MATIC": "native", "LDO": "native", "ARB": "native",
    "OP": "native", "GMX": "native", "SOL": "native", "MANTLE": "native", "LINEA": "native",
    
    # Wrapped (8): Bridge exploits, wrap/unwrap attacks
    "WBTC": "wrapped", "cBTC": "wrapped", "stETH": "wrapped", "rswETH": "wrapped",
    "CBETH": "wrapped", "LST": "wrapped", "cbRES": "wrapped", "swETH": "wrapped",
    
    # Meme/Community (7): Rug pulls, pump & dumps, coordinated dumps
    "DOGE": "meme", "SHIB": "meme", "PEPE": "meme", "FLOKI": "meme",
    "BONK": "meme", "WLD": "meme", "SAFE": "meme",
    
    # Non-ERC20 (1): Native blockchain behavior
    "ETH": "native",
}

# token-specific feature thresholds based on TYPE
# Stablecoins: LOW volatility tolerance, HIGH phishing risk
# DeFi: MEDIUM volatility, EXPLOIT risk
# Meme: HIGH volatility, RUG PULL risk
TOKEN_TYPE_THRESHOLDS = {
    "stablecoin": {
        "max_tx_volatility": 2.0,  # 200% increase is extreme
        "max_daily_activity": 500,  # More than 500 txs/day is unusual
        "min_transaction_value": 0.01,  # Below 0.01 is dust
        "unusual_tx_spike_multiplier": 10.0,  # 10x normal activity
    },
    "defi": {
        "max_tx_volatility": 5.0,  # More volatile than stables
        "max_daily_activity": 1000,
        "min_transaction_value": 0.001,
        "unusual_tx_spike_multiplier": 5.0,
    },
    "native": {
        "max_tx_volatility": 3.0,
        "max_daily_activity": 800,
        "min_transaction_value": 0.0001,
        "unusual_tx_spike_multiplier": 8.0,
    },
    "wrapped": {
        "max_tx_volatility": 4.0,
        "max_daily_activity": 1200,
        "min_transaction_value": 0.0001,
        "unusual_tx_spike_multiplier": 6.0,
    },
    "meme": {
        "max_tx_volatility": 10.0,  # Very volatile
        "max_daily_activity": 5000,  # Can have massive volume
        "min_transaction_value": 1.0,  # Pump & dumps use big amounts
        "unusual_tx_spike_multiplier": 3.0,
    },
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



def apply_rule_based_filters(features, prob_malicious, prob_poisoned, token="USDT", token_type="stablecoin", type_thresholds=None):
    """
    Apply deterministic rule-based checks to catch known attack patterns.
    Uses TOKEN_TYPE_THRESHOLDS for type-aware detection.
    
    Returns: (override_decision, override_confidence, rule_fired)
    """
    if type_thresholds is None:
        type_thresholds = TOKEN_TYPE_THRESHOLDS.get(token_type, TOKEN_TYPE_THRESHOLDS["stablecoin"])
    
    # Rule 1: NEW WALLET (< 7 days) with ANY suspicious activity
    if features.get("wallet_age_days", 100) <= 7:
        if prob_malicious > 0.3 or prob_poisoned > 0.2:
            return "REVIEW", 0.9, f"new_wallet_suspicious ({token})"
    
    # Rule 2: ULTRA-HIGH FREQUENCY + LOW VALUE (classic spam)
    # Apply type-specific activity thresholds
    max_daily = type_thresholds.get("max_daily_activity", 500)
    if features.get("tx_per_day", 0) > max_daily and features.get("avg_tx", 1000) < type_thresholds.get("min_transaction_value", 0.01):
        return "BLOCK", 0.95, f"spam_pattern_high_freq_low_value ({token} [{token_type}])"
    
    # Rule 3: NO MEANINGFUL ACTIVITY (all dust/zero transactions)
    min_tx = type_thresholds.get("min_transaction_value", 0.01)
    if features.get("avg_tx", 1000) < min_tx and features.get("tx_frequency", 0) > 10:
        return "BLOCK", 0.85, f"no_meaningful_activity ({token})"
    
    # Rule 4: INSTANT TRANSACTIONS (avg time between tx < 10 seconds = bots)
    if features.get("avg_time_between_tx_sec", 100000) < 10 and features.get("tx_frequency", 0) > 5:
        return "BLOCK", 0.80, f"bot_activity_instant_txs ({token})"
    
    # Rule 5: RECENT SPIKE IN ACTIVITY (dormant wallet suddenly active)
    # Apply type-specific spike multiplier
    spike_mult = type_thresholds.get("unusual_tx_spike_multiplier", 10.0)
    if (features.get("recent_tx", 0) > features.get("avg_tx", 1) * spike_mult and 
        features.get("wallet_age_days", 1) > 365 and
        features.get("tx_per_min", 0) > 0.1):
        return "REVIEW", 0.75, f"unusual_spike_old_wallet ({token} spike_mult={spike_mult})"
    
    # Rule 6: ABNORMAL HOUR ACTIVITY (> 20 txs/hour = unusual)
    if features.get("tx_per_hour", 0) > 20:
        return "REVIEW", 0.70, f"abnormal_tx_rate_hourly ({token})"
    
    return None, None, None





# =============================

# DECISION ENGINE (3-CLASS) + RULES

# =============================

def classify_decision(prob_malicious, prob_poisoned, conf, features, token="USDT", low_data=False):
    """
    Classify wallet risk with TOKEN-SPECIFIC thresholds.
    Different tokens have different attacker profiles and risk models.
    
    Uses:
    1. TOKEN_SCORING_RULES for trained tokens (USDT, USDC, etc.)
    2. TOKEN_TYPE_THRESHOLDS for watchonly tokens based on type
    3. Rule-based heuristics for deterministic patterns
    """
    # Get token-specific rules (default to USDT if not found)
    rules = TOKEN_SCORING_RULES.get(token, TOKEN_SCORING_RULES["USDT"])
    malicious_thresh = rules.get("malicious_threshold", 0.88)
    poisoned_thresh = rules.get("poisoned_threshold", 0.75)
    
    # Get token type for additional context (used for watchonly tokens)
    token_type = TOKEN_TYPE_CLASSIFICATION.get(token, "unknown")
    type_thresholds = TOKEN_TYPE_THRESHOLDS.get(token_type, TOKEN_TYPE_THRESHOLDS["stablecoin"])
    
    # [CRITICAL] Check VERY HIGH model confidence FIRST (skip rules if model is very certain)
    if prob_poisoned >= poisoned_thresh:
        return "BLOCK", f"Poisoned {token} wallet (high confidence - address spoofing) | Rule: {rules.get('risk_profile')}"

    if prob_malicious >= malicious_thresh:
        return "BLOCK", f"Malicious {token} wallet (high confidence - {rules.get('description')}) | Threats: {', '.join(rules.get('primary_threats', []))}"

    # Then apply rule-based filters for lower confidence cases (defensive heuristics)
    # Apply type-aware thresholds to rules
    rule_decision, rule_conf, rule_name = apply_rule_based_filters(features, prob_malicious, prob_poisoned, token, token_type, type_thresholds)
    if rule_decision:
        return rule_decision, f"{rule_name} (rule-based check for {token} [{token_type}])"

    if low_data:
        return "REVIEW", "Insufficient data"

    if features["wallet_age_days"] <= 1:
        return "REVIEW", "New wallet"

    if features["tx_per_day"] < 3:
        return "REVIEW", "Low activity"

    if conf < 0.3:
        return "REVIEW", "Low confidence"

    # Medium-high poisoning
    if prob_poisoned >= (poisoned_thresh - 0.15):
        return "BLOCK", f"Poisoned {token} wallet (medium-high confidence)"

    # Medium-high malicious
    if prob_malicious >= (malicious_thresh - 0.08):
        return "BLOCK", f"Malicious {token} wallet (high confidence)"
    
    elif prob_malicious >= 0.5:
        return "REVIEW", "Moderate malicious risk"

    return "ALLOW", "Low risk"



# =============================

# FETCH TX

# =============================

def fetch_transactions(address, debug=False):
    """
    Fetch token transactions for an address from Etherscan API.
    [CRITICAL FIX] Added debug mode to diagnose API response issues
    """
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

        response = requests.get(BASE_URL, params=params)
        data = response.json()
        result = data.get("result", [])
        
        if debug:
            print(f"[DEBUG] API Response: status={response.status_code}")
            print(f"[DEBUG] Response data: {data}")
            if isinstance(result, list) and len(result) > 0:
                print(f"[DEBUG] First TX: {result[0]}")
                print(f"[DEBUG] TX keys available: {list(result[0].keys())}")
                print(f"[DEBUG] tokenSymbol: '{result[0].get('tokenSymbol')}'")

        return result if isinstance(result, list) else []
        
    except Exception as e:
        if debug:
            print(f"[DEBUG] API Error: {e}")
        return []



# =============================

# TOKEN DETECT

# =============================

def detect_token(transactions, manual_token=None, debug=False):
    """
    Detect token from transaction list with multiple fallback strategies.
    
    [CRITICAL FIX] Now tries multiple detection methods:
    1. Manual override if provided by user
    2. Symbol detection (tokenSymbol field)
    3. Contract address matching (fallback if symbols are empty)
    4. Returns token if in TRAINED_TOKENS list, None otherwise
    """
    
    # Strategy 1: Use manual override if provided
    if manual_token:
        manual_token_upper = manual_token.upper().strip()
        if manual_token_upper in SUPPORTED_TOKENS:
            print(f"[OK] Using manual token override: {manual_token_upper}")
            return manual_token_upper
        elif manual_token_upper in ALL_TOKENS:
            print(f"[WARN] Token {manual_token_upper} detected but not trained (no model available)")
            return None
        else:
            print(f"[ERROR] Unknown token: {manual_token_upper}")
            return None
    
    counts_by_symbol = {}
    counts_by_contract = {}
    contract_to_token = {addr.lower(): token for token, addr in ALL_TOKENS.items()}
    
    if debug:
        print(f"[DEBUG] Processing {len(transactions[:20])} transactions for token detection")
    
    # Check top 20 most recent transactions
    for i, tx in enumerate(transactions[:20]):
        if not isinstance(tx, dict):
            continue
        
        # Strategy 2: Try symbol-based detection first
        sym = tx.get("tokenSymbol", "")
        if isinstance(sym, str) and sym:
            sym = sym.upper().strip()
            if sym in ALL_TOKENS:
                counts_by_symbol[sym] = counts_by_symbol.get(sym, 0) + 1
                if debug and i < 3:
                    print(f"[DEBUG] TX {i}: Symbol '{sym}' found")
                continue
        
        # Strategy 3: Fallback to contract address matching
        contract = tx.get("contractAddress", "").lower()
        if contract and contract in contract_to_token:
            token = contract_to_token[contract]
            counts_by_contract[token] = counts_by_contract.get(token, 0) + 1
            if debug and i < 3:
                print(f"[DEBUG] TX {i}: Contract {contract[:10]}... → {token}")
        elif debug and i < 3 and contract:
            print(f"[DEBUG] TX {i}: Contract {contract[:10]}... not recognized, symbol='{sym}'")
    
    # Combine results: prefer symbol detection, fallback to contract
    all_counts = {**counts_by_contract, **counts_by_symbol}
    
    if not all_counts:
        print(f"[WARN] No recognized tokens found in transaction history")
        if debug:
            print(f"[DEBUG] Checked {len(transactions[:20])} transactions")
            if transactions:
                print(f"[DEBUG] Sample TX contractAddress: '{transactions[0].get('contractAddress')}'")
                print(f"[DEBUG] Sample TX tokenSymbol: '{transactions[0].get('tokenSymbol')}'")
        return None
    
    # Find most common token
    detected_token = max(all_counts, key=all_counts.get)
    count = all_counts[detected_token]
    
    if debug:
        print(f"[DEBUG] Token counts: {all_counts}")
    
    # Check if it's a trained token
    if detected_token in SUPPORTED_TOKENS:
        print(f"[OK] Found TRAINED token: {detected_token} (count: {count}) - Scoring enabled")
        return detected_token
    else:
        # It's a watchonly token - report but don't score
        other_tokens = [f"{t} ({all_counts[t]})" for t in sorted(all_counts.keys()) if t != detected_token]
        other_str = f" | Other detected: {', '.join(other_tokens)}" if other_tokens else ""
        print(f"[WARN] Detected token: {detected_token} (count: {count}) - UNSUPPORTED (no model trained){other_str}")
        print(f"[SKIP] {detected_token} wallet scoring disabled - model not available")
        return None



# =============================

# FEATURE GEN - ALL 19 FEATURES

# =============================



def _compute_graph_features(wallet_address, transactions):
    """
    🧠 Compute graph features for wallet from transactions
    Returns dictionary of graph metrics
    """
    if not TransactionGraph or not transactions or not wallet_address:
        return {
            'graph_degree': 0,
            'graph_pagerank': 0.0,
            'graph_clustering': 0.0,
            'graph_betweenness': 0.0,
            'graph_unique_counterparties': 0,
            'graph_inflow': 0.0,
            'graph_outflow': 0.0,
            'connected_to_malicious': 0
        }
    
    try:
        graph = TransactionGraph(directed=True)
        
        for tx in transactions:
            try:
                sender = tx.get("from", "").lower()
                recipient = tx.get("to", "").lower()
                
                if not sender or not recipient:
                    continue
                
                amount = int(tx.get("value", 0)) / (10 ** int(tx.get("tokenDecimal", 18)))
                graph.add_transaction(sender, recipient, amount)
            except:
                continue
        
        features = graph.extract_features(wallet_address.lower())
        return features
        
    except Exception as e:
        return {
            'graph_degree': 0,
            'graph_pagerank': 0.0,
            'graph_clustering': 0.0,
            'graph_betweenness': 0.0,
            'graph_unique_counterparties': 0,
            'graph_inflow': 0.0,
            'graph_outflow': 0.0,
            'connected_to_malicious': 0
        }


def _compute_advanced_features(txs):
    """
    🧠 ADVANCED FEATURE ENGINEERING - Temporal, behavioral, value, sequence patterns
    """
    try:
        if len(txs) < 3:
            return _get_empty_advanced_features_wallet()
        
        rows = []
        senders = []
        receivers = []
        values = []
        timestamps = []
        
        for tx in txs:
            try:
                amount = int(tx.get("value", 0)) / (10 ** int(tx.get("tokenDecimal", 18)))
                if amount <= 0:
                    continue
                
                timestamp = int(tx.get("timeStamp", 0))
                sender = tx.get("from", "").lower()
                receiver = tx.get("to", "").lower()
                
                if sender and receiver:
                    rows.append({
                        'amount': amount,
                        'timestamp': timestamp,
                        'sender': sender,
                        'receiver': receiver
                    })
                    senders.append(sender)
                    receivers.append(receiver)
                    values.append(amount)
                    timestamps.append(timestamp)
            except:
                continue
        
        if len(rows) < 3:
            return _get_empty_advanced_features_wallet()
        
        df = pd.DataFrame(rows)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        df = df.sort_values('timestamp')
        
        # TEMPORAL FEATURES
        time_diffs = df['timestamp'].diff().dt.total_seconds().fillna(0).values
        burst_threshold = 60
        burst_count = np.sum(time_diffs < burst_threshold)
        burst_ratio = burst_count / len(time_diffs) if len(time_diffs) > 0 else 0
        
        inter_arrival_var = np.var(time_diffs[time_diffs > 0]) if np.sum(time_diffs > 0) > 1 else 0
        
        active_hours = df['timestamp'].dt.hour.value_counts()
        hours_active = len(active_hours)
        hour_concentration = active_hours.max() / len(df) if len(df) > 0 else 0
        
        # BEHAVIORAL FEATURES
        from collections import Counter
        
        unique_senders = len(set(senders))
        sender_entropy = -np.sum((np.array(list(Counter(senders).values())) / len(senders)) * 
                                 np.log2(np.array(list(Counter(senders).values())) / len(senders) + 1e-10))
        
        unique_receivers = len(set(receivers))
        receiver_entropy = -np.sum((np.array(list(Counter(receivers).values())) / len(receivers)) *
                                   np.log2(np.array(list(Counter(receivers).values())) / len(receivers) + 1e-10))
        
        direction_ratio = unique_senders / unique_receivers if unique_receivers > 0 else unique_senders
        
        # VALUE-BASED FEATURES
        p25 = np.percentile(values, 25)
        p50 = np.percentile(values, 50)
        p75 = np.percentile(values, 75)
        p95 = np.percentile(values, 95)
        
        max_spike_ratio = np.max(values) / (p50 if p50 > 0 else 1)
        
        mean_val = np.mean(values)
        median_val = p50
        median_mean_ratio = mean_val / (median_val if median_val > 0 else 1)
        
        recent_values = df['amount'].iloc[-5:].sum()
        total_values = df['amount'].sum()
        recent_concentration = recent_values / (total_values if total_values > 0 else 1)
        
        # SEQUENCE FEATURES
        send_back_count = 0
        for i in range(len(df) - 1):
            curr_sender = df.iloc[i]['sender']
            curr_receiver = df.iloc[i]['receiver']
            next_sender = df.iloc[i + 1]['sender']
            next_receiver = df.iloc[i + 1]['receiver']
            
            if (curr_sender == next_receiver and curr_receiver == next_sender):
                send_back_count += 1
        
        send_back_ratio = send_back_count / max(len(df) - 1, 1)
        
        flow_pairs = [(row['sender'], row['receiver']) for _, row in df.iterrows()]
        flow_counts = Counter(flow_pairs)
        cyclic_flows = sum(1 for count in flow_counts.values() if count > 2)
        cyclic_ratio = cyclic_flows / len(flow_counts) if len(flow_counts) > 0 else 0
        
        repeat_receiver_ratio = len([c for c in Counter(receivers).values() if c > 3]) / unique_receivers if unique_receivers > 0 else 0
        
        return {
            'temporal_burst_ratio': float(burst_ratio),
            'temporal_inter_arrival_var': float(inter_arrival_var),
            'temporal_hours_active': int(hours_active),
            'temporal_hour_concentration': float(hour_concentration),
            'behavioral_unique_senders': int(unique_senders),
            'behavioral_sender_entropy': float(sender_entropy),
            'behavioral_unique_receivers': int(unique_receivers),
            'behavioral_receiver_entropy': float(receiver_entropy),
            'behavioral_direction_ratio': float(direction_ratio),
            'value_p25': float(p25),
            'value_p50': float(p50),
            'value_p75': float(p75),
            'value_p95': float(p95),
            'value_max_spike_ratio': float(max_spike_ratio),
            'value_median_mean_ratio': float(median_mean_ratio),
            'value_recent_concentration': float(recent_concentration),
            'sequence_send_back_ratio': float(send_back_ratio),
            'sequence_cyclic_ratio': float(cyclic_ratio),
            'sequence_repeat_receiver_ratio': float(repeat_receiver_ratio),
        }
    except Exception as e:
        return _get_empty_advanced_features_wallet()


def _get_empty_advanced_features_wallet():
    """Return default advanced features for wallet_check"""
    return {
        'temporal_burst_ratio': 0.0,
        'temporal_inter_arrival_var': 0.0,
        'temporal_hours_active': 0,
        'temporal_hour_concentration': 0.0,
        'behavioral_unique_senders': 0,
        'behavioral_sender_entropy': 0.0,
        'behavioral_unique_receivers': 0,
        'behavioral_receiver_entropy': 0.0,
        'behavioral_direction_ratio': 0.0,
        'value_p25': 0.0,
        'value_p50': 0.0,
        'value_p75': 0.0,
        'value_p95': 0.0,
        'value_max_spike_ratio': 0.0,
        'value_median_mean_ratio': 0.0,
        'value_recent_concentration': 0.0,
        'sequence_send_back_ratio': 0.0,
        'sequence_cyclic_ratio': 0.0,
        'sequence_repeat_receiver_ratio': 0.0,
    }


def explain_wallet_decision(model, scaled_features, features_dict, feature_names, token="USDT", max_display=10):
    """
    🧠 EXPLAINABILITY - SHAP-based explanations for wallet scoring decisions
    
    Generates human-readable explanations for why a wallet is flagged
    Shows feature importance and contribution to final decision
    
    Args:
        model: Trained ML model
        scaled_features: Scaled feature array for model
        features_dict: Original features dictionary
        feature_names: List of feature column names
        token: Token being scored
        max_display: Maximum features to display in explanation
        
    Returns:
        Dictionary with explanation data:
        - summary: Human-readable summary
        - top_features: List of most important features with values
        - contributions: Feature contributions to score (if SHAP available)
    """
    if not HAS_SHAP:
        # Fallback without SHAP: just show top features
        return {
            'summary': "Explanation unavailable (SHAP not installed). Install with: pip install shap",
            'top_features': [],
            'contributions': [],
            'method': 'fallback'
        }
    
    try:
        # Determine model type for appropriate explainer
        if hasattr(model, 'estimators_'):
            # RandomForest or ensemble
            explainer = shap.TreeExplainer(model)
        else:
            # Generic explainer
            explainer = shap.KernelExplainer(
                model.predict_proba if hasattr(model, 'predict_proba') else model.predict,
                scaled_features[:min(100, len(scaled_features))]  # Use sample for background
            )
        
        # Compute SHAP values
        shap_values = explainer.shap_values(scaled_features)
        
        # Handle multi-class (shap_values is list for multi-class)
        if isinstance(shap_values, list):
            shap_values = shap_values[1]  # Use malicious class
        
        # Get feature importance (mean absolute SHAP value)
        importances = np.abs(shap_values[0]).mean(axis=0) if shap_values.ndim > 1 else np.abs(shap_values)
        
        # Top features
        top_indices = np.argsort(importances)[-max_display:][::-1]
        top_features = [
            {
                'name': feature_names[i],
                'importance': float(importances[i]),
                'value': float(scaled_features[0][i]),
                'original_value': features_dict.get(feature_names[i], 'N/A')
            }
            for i in top_indices
        ]
        
        # Build explanation summary
        risk_factors = []
        safe_factors = []
        
        for feat in top_features[:5]:
            if feat['value'] > 0.5:  # Normalized scale
                risk_factors.append(f"High {feat['name'].replace('_', ' ')}")
            else:
                safe_factors.append(f"Low {feat['name'].replace('_', ' ')}")
        
        if risk_factors:
            summary = f"Flagged due to: {', '.join(risk_factors[:2])}"
        elif safe_factors:
            summary = f"Safe indicators: {', '.join(safe_factors[:2])}"
        else:
            summary = "Mixed risk signals detected"
        
        return {
            'summary': summary,
            'top_features': top_features,
            'contributions': [{'feature': f['name'], 'impact': f['importance']} for f in top_features],
            'method': 'shap_tree' if hasattr(model, 'estimators_') else 'shap_kernel',
            'model_type': type(model).__name__
        }
        
    except Exception as e:
        # Graceful fallback
        return {
            'summary': f"Explanation generation failed: {str(e)}",
            'top_features': [],
            'contributions': [],
            'method': 'error',
            'error': str(e)
        }


def generate_features(transactions, wallet_address=None):
    """
    Generate all 19 features used by the trained models.
    Includes base features (8) + V3 poisoning features (4) + advanced heuristics (7) + graph features (8).
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

    # 🧠 GRAPH FEATURES - Network Intelligence
    graph_features = _compute_graph_features(wallet_address, transactions)

    # 🧠 ADVANCED FEATURES - Temporal, behavioral, value, sequence patterns
    advanced_features = _compute_advanced_features(transactions)

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
            "short_time_window": 0,
            **graph_features,  # Add graph features
            **advanced_features  # Add advanced features
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
        "short_time_window": int(short_time_window),
        **graph_features,  # Add graph features
        **advanced_features  # Add advanced features
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

def score_wallet(address, manual_token=None, debug=False):
    """
    Score wallet risk using trained ML models with token-specific thresholds.
    
    [CRITICAL FIX] New parameters:
    - manual_token: Allow users to manually specify token (e.g., "USDT") for debugging
    - debug: Enable verbose debugging of API responses and token detection
    
    Example: score_wallet("0x...", manual_token="USDT", debug=True)
    """
    total_start = time.time()
    
    if debug:
        print(f"[DEBUG] Starting wallet_check for {address}")
        print(f"[DEBUG] manual_token={manual_token}, debug={debug}")

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



            decision, reason = classify_decision(prob_malicious, prob_poisoned, conf, features, token=token)



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

    txs = fetch_transactions(address, debug=debug)

    print(f"? API TIME: {time.time() - api_start:.3f}s")

    if not txs:
        print(f"[ERROR] No transactions found via API for {address}")
        if debug:
            print(f"[DEBUG] This could mean:")
            print(f"[DEBUG] 1. Wallet has no token transfers")
            print(f"[DEBUG] 2. API rate limit or connectivity issue")
            print(f"[DEBUG] 3. Wrong API key configured")
        print(f"? TOTAL TIME: {time.time() - total_start:.3f}s")
        return

    token = detect_token(txs, manual_token=manual_token, debug=debug)
    if not token:
        print(f"[ERROR] Scoring skipped - no supported token model available")
        if debug:
            print(f"[DEBUG] Detected transactions but no recognized TRAINED token")
            print(f"[DEBUG] Available TRAINED tokens: {SUPPORTED_TOKENS}")
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



    decision, reason = classify_decision(prob_malicious, prob_poisoned, conf, features, token=token)



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
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="Score wallet risk using ML models")
    parser.add_argument("address", nargs="?", help="Wallet address to score (0x...)")
    parser.add_argument("--token", type=str, help="[FIX] Manual token override (e.g., USDT, USDC)")
    parser.add_argument("--debug", action="store_true", help="[FIX] Enable debug mode for diagnostics")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode (default if no address provided)")
    
    args = parser.parse_args()
    
    print("? FINAL SYSTEM")
    
    # If address provided as CLI arg, score it directly
    if args.address:
        print(f"\n[CLI] Scoring wallet: {args.address}")
        if args.token:
            print(f"[CLI] Manual token override: {args.token}")
        if args.debug:
            print(f"[CLI] Debug mode ENABLED")
        score_wallet(args.address, manual_token=args.token, debug=args.debug)
    else:
        # Interactive mode
        while True:

            w = input("\nWallet (or 'exit'): ")

            if w.lower() == "exit":
                break

            if not w.startswith("0x"):
                print("[ERROR] Invalid address (must start with 0x)")
                continue

            # In interactive mode, ask for token override if desired
            token_override = input("Token override (press Enter for auto-detect, or type USDT/USDC/etc): ").strip().upper() or None
            
            debug_mode = input("Enable debug mode? (y/n): ").strip().lower() == "y"

            score_wallet(w, manual_token=token_override, debug=debug_mode)

            time.sleep(0.3)
