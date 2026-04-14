import requests
import pandas as pd
import os
import time
import numpy as np

API_KEY = "YOUR_API_KEY"
BASE_URL = "https://api.etherscan.io/v2/api"

os.makedirs("datasets", exist_ok=True)

# =========================================================
# 🔥 ENABLE TOGGLES (CONTROL OUTPUT CSVs)
# =========================================================
ENABLE_V0 = True   # Broad baseline dataset
ENABLE_V1 = True   # High-trust malicious (manual labeling stage)
ENABLE_V2 = True   # Scaled malicious dataset
ENABLE_V3 = True   # Poisoning behavior detection dataset

# =========================================================
# 🔥 WALLET SOURCE CONTROL (POOL vs SEEDS)
# =========================================================
USE_POOL_V0 = True
USE_POOL_V1 = False
USE_POOL_V2 = True
USE_POOL_V3 = False

# =========================================================
# 🔥 POOL FILES (SEPARATED PER VERSION)
# =========================================================
POOL_FILES = {
    "v0": "v0_wallet_pool.csv",
    "v1": "v1_wallet_pool.csv",
    "v2": "v2_wallet_pool.csv",
    "v3": "v3_wallet_pool.csv"
}

# =========================================================
# 🔥 CONFIG PER VERSION (FULL CONTROL)
# =========================================================

# =========================================================
# V0 → BROAD BASELINE (DONE)
# - Goal: Learn NORMAL wallet behavior
# - Output: Mostly SAFE wallets
# - Label: 0
# =========================================================
CONFIG_V0 = {
    "MAX_TOTAL_WALLETS": 16000,
    "MAX_WALLETS_PER_SOURCE": 20,
    "SEEDS": [
        # put active wallets here if not using pool
    ]
}

# =========================================================
# V1 → HIGH-TRUST MALICIOUS (DONE)
# - Goal: Manually verified bad wallets
# - Output: Needs manual labeling
# - Label: None → later curated
# =========================================================
CONFIG_V1 = {
    "MAX_TOTAL_WALLETS": 2000,
    "MAX_WALLETS_PER_SOURCE": 10,
    "SEEDS": [
        # your known suspicious wallets
    ]
}

# =========================================================
# V2 → SCALED MALICIOUS (CRAWLING)
# - Goal: Expand malicious clusters
# - Output: Large noisy dataset
# - Label: None → semi-supervised
# =========================================================
CONFIG_V2 = {
    "MAX_TOTAL_WALLETS": 50000,
    "MAX_WALLETS_PER_SOURCE": 25,
    "SEEDS": [
        # seeds from V1 ideally
    ]
}

# =========================================================
# V3 → POISONING BEHAVIOR (CRITICAL)
# - Goal: Detect address poisoning attacks
# - Output: Auto-labeled malicious (label=2)
# =========================================================
CONFIG_V3 = {
    "MAX_TOTAL_WALLETS": 6000,
    "MAX_WALLETS_PER_SOURCE": 50,
    "SEEDS": [
        "0xdc4858741e738bb304fc5b290e7b9453da6a5baa"
    ],
    "dust_threshold": 0.001,
    "dust_ratio": 0.3,
    "sender_ratio": 0.5
}

# =========================================================
# LOAD / SAVE POOL
# =========================================================
def load_pool(path):
    if os.path.exists(path):
        df = pd.read_csv(path)
        if "wallet" in df.columns:
            return df["wallet"].dropna().tolist()
    return []

def save_pool(wallets, path):
    pd.DataFrame(list(set(wallets)), columns=["wallet"]).to_csv(path, index=False)

# =========================================================
# FETCH TRANSACTIONS
# =========================================================
def fetch_txs(address):
    try:
        res = requests.get(BASE_URL, params={
            "chainid": 1,
            "module": "account",
            "action": "tokentx",
            "address": address,
            "offset": 100,
            "sort": "desc",
            "apikey": API_KEY
        }).json()

        result = res.get("result")
        return result if isinstance(result, list) else []
    except:
        return []

# =========================================================
# EXPAND WALLET NETWORK
# =========================================================
def expand_wallets(config, version, use_pool):
    pool_file = POOL_FILES[version]

    if use_pool:
        wallets = load_pool(pool_file)
        if wallets:
            print(f"📂 {version.upper()} using pool: {len(wallets)}")
            return wallets

    seeds = config["SEEDS"]

    if not seeds:
        print(f"⚠️ {version.upper()} NO SEEDS → EMPTY OUTPUT")
        return []

    visited = set(seeds)
    frontier = list(seeds)

    print(f"🌱 {version.upper()} seeds: {len(seeds)}")

    while frontier and len(visited) < config["MAX_TOTAL_WALLETS"]:
        new_frontier = []

        for wallet in frontier:
            txs = fetch_txs(wallet)

            neighbors = set()
            for tx in txs:
                neighbors.add(tx.get("from"))
                neighbors.add(tx.get("to"))

            neighbors = [
                w for w in neighbors
                if isinstance(w, str)
                and w.startswith("0x")
                and len(w) == 42
            ]

            neighbors = neighbors[:config["MAX_WALLETS_PER_SOURCE"]]

            for n in neighbors:
                if n not in visited:
                    visited.add(n)
                    new_frontier.append(n)

                if len(visited) >= config["MAX_TOTAL_WALLETS"]:
                    break

            time.sleep(0.2)

        frontier = new_frontier

    wallets = list(visited)
    save_pool(wallets, pool_file)

    print(f"📊 {version.upper()} collected: {len(wallets)}")
    return wallets

# =========================================================
# BASE FEATURES (USED BY V0/V1/V2/V3)
# =========================================================
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
        "wallet_age_days": wallet_age,
        "avg_tx": np.mean(df["amount"]),
        "recent_tx": df["amount"].iloc[-1],
        "tx_frequency": len(df) / wallet_age,
        "tx_per_min": len(df) / (total_seconds / 60),
        "tx_per_hour": len(df) / (total_seconds / 3600),
        "tx_per_day": len(df) / (total_seconds / 86400),
        "avg_time_between_tx_sec": df["time_diff"].mean()
    }

# =========================================================
# V3 POISON FEATURES
# =========================================================
def compute_v3_features(txs, wallet, config):
    dust = 0
    senders = set()
    similarity_hits = 0

    for tx in txs:
        try:
            sender = tx["from"]
            value = int(tx["value"]) / (10 ** int(tx["tokenDecimal"]))

            senders.add(sender)

            if value < config["dust_threshold"]:
                dust += 1

            if wallet[:6] == sender[:6] and wallet[-4:] == sender[-4:]:
                similarity_hits += 1
        except:
            continue

    total = len(txs)
    if total == 0:
        return 0, 0, 0, 0

    dust_ratio = dust / total
    new_sender_ratio = len(senders) / total

    poisoned = int(
        dust_ratio > config["dust_ratio"] and
        similarity_hits > 0 and
        new_sender_ratio > config["sender_ratio"]
    )

    return dust_ratio, similarity_hits, new_sender_ratio, poisoned

# =========================================================
# RUNNERS
# =========================================================
def run_v0():
    wallets = expand_wallets(CONFIG_V0, "v0", USE_POOL_V0)
    rows = []

    for w in wallets:
        txs = fetch_txs(w)
        base = compute_base_features(txs)
        if base:
            rows.append({"wallet": w, **base, "label": 0})

    pd.DataFrame(rows).to_csv("datasets/v0.csv", index=False)
    print(f"✅ V0 DONE ({len(rows)})")

def run_v1():
    wallets = expand_wallets(CONFIG_V1, "v1", USE_POOL_V1)
    rows = []

    for w in wallets:
        txs = fetch_txs(w)
        base = compute_base_features(txs)
        if base:
            rows.append({"wallet": w, **base, "label": None})

    pd.DataFrame(rows).to_csv("datasets/v1.csv", index=False)
    print(f"✅ V1 DONE ({len(rows)})")

def run_v2():
    wallets = expand_wallets(CONFIG_V2, "v2", USE_POOL_V2)
    rows = []

    for w in wallets:
        txs = fetch_txs(w)
        base = compute_base_features(txs)
        if base:
            rows.append({"wallet": w, **base, "label": None})

    pd.DataFrame(rows).to_csv("datasets/v2.csv", index=False)
    print(f"✅ V2 DONE ({len(rows)})")

def run_v3():
    wallets = expand_wallets(CONFIG_V3, "v3", USE_POOL_V3)
    rows = []

    for w in wallets:
        txs = fetch_txs(w)
        base = compute_base_features(txs)
        if not base:
            continue

        d, s, n, p = compute_v3_features(txs, w, CONFIG_V3)

        rows.append({
            "wallet": w,
            **base,
            "dust_tx_ratio": d,
            "similarity_hits": s,
            "new_sender_ratio": n,
            "is_poisoned_pattern": p,
            "label": 2 if p else -1
        })

    df = pd.DataFrame(rows)
    df.to_csv("datasets/v3_raw.csv", index=False)
    df[df["label"] == 2].to_csv("datasets/v3_clean.csv", index=False)

    print(f"🔥 V3 DONE ({len(rows)})")

# =========================================================
# MAIN EXECUTION
# =========================================================
if ENABLE_V0: run_v0()
if ENABLE_V1: run_v1()
if ENABLE_V2: run_v2()
if ENABLE_V3: run_v3()

print("\n🔥 ALL DATASETS GENERATED")