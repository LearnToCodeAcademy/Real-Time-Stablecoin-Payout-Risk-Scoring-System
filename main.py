import requests
import pandas as pd
import os
import time
import shutil
###test 
API_KEY = "HP8KE56GFDIDIUCEGPAI9T5DCDYWIPYW4K"
BASE_URL = "https://api.etherscan.io/v2/api"

# =============================
# 🔥 MODE SWITCH
# =============================
MODE = "expand"   # "expand" or "extract"

# =============================
# CONFIG
# =============================
ACTIVE_COINS = {
    "usdt": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
    "usdc": "0xA0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
}

RUN_ETH = True

MAX_TOTAL_WALLETS = 4300
MAX_WALLETS_PER_SOURCE = 5

MEV_ADDRESS = "0xBdb3ba9ffe392549E1f8658DD2630c141fDF47B6"
PYUSD_CONTRACT = "0x6c3ea9036406852006290770BEdFcAbA0e23A0e8"

SEED_WALLETS = [
    MEV_ADDRESS,
    PYUSD_CONTRACT,
    "0x99e096F18fbFF2808f7388859b387fdD056a3589"
]

WALLET_POOL_FILE = "wallet_pool_label.csv"

os.makedirs("datasets", exist_ok=True)
os.makedirs("backups", exist_ok=True)

# =============================
# LOAD / SAVE
# =============================
def load_wallets():
    if os.path.exists(WALLET_POOL_FILE):
        return pd.read_csv(WALLET_POOL_FILE)["wallet"].tolist()
    return SEED_WALLETS.copy()

def save_wallets(wallets):
    pd.DataFrame(list(set(wallets)), columns=["wallet"]).to_csv(WALLET_POOL_FILE, index=False)

# =============================
# SAFE FETCH
# =============================
def safe_fetch(params):
    try:
        data = requests.get(BASE_URL, params=params).json()
        result = data.get("result")
        if not isinstance(result, list):
            return []
        return result
    except:
        return []

def fetch_token_transactions(address):
    return safe_fetch({
        "chainid": 1,
        "module": "account",
        "action": "tokentx",
        "address": address,
        "offset": 100,
        "sort": "desc",
        "apikey": API_KEY
    })

def fetch_eth_transactions(address):
    return safe_fetch({
        "chainid": 1,
        "module": "account",
        "action": "txlist",
        "address": address,
        "offset": 100,
        "sort": "desc",
        "apikey": API_KEY
    })

# =============================
# WALLET EXTRACTION
# =============================
def extract_wallets_limited(transactions, limit=300):
    wallets = set()

    if not transactions:
        return wallets

    for tx in transactions:
        try:
            wallets.add(tx.get("from"))
            wallets.add(tx.get("to"))
            wallets.discard(None)

            if len(wallets) >= limit:
                break
        except:
            continue

    return wallets

# =============================
# FILTER
# =============================
def is_valid_wallet(df):
    if df.empty:
        return False
    if len(df) < 5:
        return False
    if df["amount"].sum() == 0:
        return False
    if df["amount"].mean() < 0.001:
        return False
    if len(df) > 1000:
        return False
    return True

# =============================
# PROCESS
# =============================
def process_token_transactions(transactions, contract):
    result = []
    for tx in transactions:
        try:
            if tx["contractAddress"].lower() != contract.lower():
                continue

            result.append({
                "amount": int(tx["value"]) / (10 ** int(tx["tokenDecimal"])),
                "timestamp": int(tx["timeStamp"])
            })
        except:
            continue
    return result

def process_eth_transactions(transactions):
    result = []
    for tx in transactions:
        try:
            result.append({
                "amount": int(tx["value"]) / (10 ** 18),
                "timestamp": int(tx["timeStamp"])
            })
        except:
            continue
    return result

# =============================
# FEATURES
# =============================
def add_time_features(df):
    df = df.sort_values("timestamp")
    df["time_diff"] = df["timestamp"].diff().dt.total_seconds().fillna(0)

    total_seconds = max((df["timestamp"].max() - df["timestamp"].min()).total_seconds(), 1)

    return {
        "tx_per_min": len(df) / (total_seconds / 60),
        "tx_per_hour": len(df) / (total_seconds / 3600),
        "tx_per_day": len(df) / (total_seconds / 86400),
        "avg_time_between_tx_sec": df["time_diff"].mean()
    }

def generate_features(df):
    if df.empty:
        return None

    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")

    wallet_age = (df["timestamp"].max() - df["timestamp"].min()).days
    avg_tx = df["amount"].mean()
    recent_tx = df["amount"].iloc[0]
    freq = len(df) / max(wallet_age, 1)

    return {
        "wallet_age_days": wallet_age,
        "avg_tx": avg_tx,
        "recent_tx": recent_tx,
        "tx_frequency": freq,
        **add_time_features(df)
    }

# =============================
# MAIN
# =============================
wallets = load_wallets()
all_wallets = set(wallets)

print(f"🔥 Starting with {len(wallets)} wallets | MODE: {MODE}")

for name, contract in ACTIVE_COINS.items():
    print(f"\n===== {name.upper()} =====")
    rows = []

    for wallet in wallets:

        # 🚫 Limit only applies in expansion mode
        if MODE == "expand" and len(all_wallets) >= MAX_TOTAL_WALLETS:
            print("🚫 Reached wallet limit")
            break

        txs = fetch_token_transactions(wallet)

        # 🔥 EXPANSION MODE
        if MODE == "expand":
            new_wallets = extract_wallets_limited(txs, MAX_WALLETS_PER_SOURCE)
            all_wallets.update(new_wallets)

        # 🔥 EXTRACTION MODE
        if MODE == "extract":
            processed = process_token_transactions(txs, contract)
            if not processed:
                continue

            df = pd.DataFrame(processed)
            if not is_valid_wallet(df):
                continue

            features = generate_features(df)

            if features:
                features["wallet"] = wallet
                features["token"] = name

                if wallet == MEV_ADDRESS:
                    features["source"] = "mev"
                elif wallet == PYUSD_CONTRACT:
                    features["source"] = "pyusd"
                else:
                    features["source"] = "normal"

                rows.append(features)

        time.sleep(0.2)

    # 💾 SAVE only in extract mode
    if MODE == "extract" and rows:
        pd.DataFrame(rows).to_csv(f"datasets/{name}_datasets.csv", index=False)
        print(f"✅ Saved {name}")

# SAVE wallet pool always
save_wallets(all_wallets)

print(f"🚀 Wallet pool size: {len(all_wallets)}")