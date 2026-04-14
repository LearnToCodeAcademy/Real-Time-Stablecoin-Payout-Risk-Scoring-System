import requests
import pandas as pd
import os
import time

API_KEY = "HP8KE56GFDIDIUCEGPAI9T5DCDYWIPYW4K"
BASE_URL = "https://api.etherscan.io/v2/api"

MODE = "expand"  # "expand" or "extract"

# 🔥 NEW TOGGLE
USE_WALLET_POOL = True   # True = use CSV, False = use seeds only

# 🔥 HARD-CODED SEEDS (used if toggle = False OR pool empty)
SEED_WALLETS = [
    "0xdc4858741e738bb304fc5b290e7b9453da6a5baa",
    "0x3D0f22BF11636CC9cb129e2B261EEd35a487455C"
]

ACTIVE_COINS = {
    "usdt": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
    "usdc": "0xA0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
}

MAX_TOTAL_WALLETS = 6000
MAX_WALLETS_PER_SOURCE = 30

WALLET_POOL_FILE = "wallet_pool_label.csv"

os.makedirs("datasets", exist_ok=True)

# =============================
# LOAD / SAVE
# =============================
def load_wallets():
    if os.path.exists(WALLET_POOL_FILE):
        df = pd.read_csv(WALLET_POOL_FILE)
        if "wallet" in df.columns:
            return df["wallet"].dropna().tolist()
    return []

def save_wallets(wallets):
    pd.DataFrame(list(set(wallets)), columns=["wallet"]).to_csv(WALLET_POOL_FILE, index=False)

# =============================
# FETCH
# =============================
def fetch_token_transactions(address):
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

# =============================
# EXPANSION
# =============================
def extract_wallets(transactions):
    wallets = set()

    for tx in transactions:
        wallets.add(tx.get("from"))
        wallets.add(tx.get("to"))

    return {
        w for w in wallets
        if isinstance(w, str) and w.startswith("0x") and len(w) == 42
    }

# =============================
# V3 FEATURES
# =============================
def compute_poison_features(txs, wallet):
    dust = 0
    senders = set()
    similarity_hits = 0

    for tx in txs:
        try:
            sender = tx["from"]
            value = int(tx["value"]) / (10 ** int(tx["tokenDecimal"]))

            senders.add(sender)

            if value < 0.001:
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
        dust_ratio > 0.3 and
        similarity_hits > 0 and
        new_sender_ratio > 0.5
    )

    return dust_ratio, similarity_hits, new_sender_ratio, poisoned

# =============================
# MAIN
# =============================

# 🔥 WALLET SOURCE LOGIC
wallets = []

if USE_WALLET_POOL:
    wallets = load_wallets()
    print(f"📂 Loaded {len(wallets)} wallets from pool")

# fallback if empty OR disabled
if not wallets:
    wallets = SEED_WALLETS
    print(f"🌱 Using seed wallets: {len(wallets)}")

all_wallets = set(wallets)

print(f"🚀 Starting with {len(wallets)} wallets | MODE: {MODE}")

rows = []

for wallet in wallets:

    if len(all_wallets) >= MAX_TOTAL_WALLETS:
        print("🚫 Reached max wallet cap")
        break

    txs = fetch_token_transactions(wallet)

    if not txs:
        continue

    # =============================
    # EXPAND
    # =============================
    if MODE == "expand":
        neighbors = extract_wallets(txs)
        neighbors = list(neighbors)[:MAX_WALLETS_PER_SOURCE]

        all_wallets.update(neighbors)

    # =============================
    # EXTRACT (V3)
    # =============================
    if MODE == "extract":

        d, s, n, p = compute_poison_features(txs, wallet)

        rows.append({
            "wallet": wallet,
            "dust_tx_ratio": d,
            "similarity_hits": s,
            "new_sender_ratio": n,
            "is_poisoned_pattern": p,
            "label": 2 if p else -1
        })

    time.sleep(0.2)

# =============================
# SAVE
# =============================
save_wallets(all_wallets)

if MODE == "extract":
    df = pd.DataFrame(rows)
    df.to_csv("datasets/v3_raw.csv", index=False)

    df_clean = df[df["label"] == 2]
    df_clean.to_csv("datasets/usdt_labeled_v3.csv", index=False)

    print(f"🔥 V3 DONE → {len(df_clean)} poisoned wallets")

print(f"📊 Wallet pool: {len(all_wallets)}")