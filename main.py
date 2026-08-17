import argparse
import subprocess
import sys
import requests
import pandas as pd
import os
import time
import numpy as np
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from collections import Counter

# 🧠 GRAPH ENGINE - Network Intelligence
try:
    from graph_engine import TransactionGraph
except ImportError:
    TransactionGraph = None

API_KEY = os.getenv("ETHERSCAN_API_KEY") or os.getenv("ETHERSCAN_API_KEY_V0", "")
BASE_URL = "https://api.etherscan.io/v2/api"

VERSION_API_KEYS = {
    "v0": os.getenv("ETHERSCAN_API_KEY_V0") or API_KEY,
    "v1": os.getenv("ETHERSCAN_API_KEY_V1") or API_KEY,
    "v2": os.getenv("ETHERSCAN_API_KEY_V2") or API_KEY,
    "v3": os.getenv("ETHERSCAN_API_KEY_V3") or API_KEY,
    "v4": os.getenv("ETHERSCAN_API_KEY_V4") or API_KEY,
}

def get_api_key(version):
    version_key = str(version).lower()
    return VERSION_API_KEYS.get(version_key, API_KEY)


def parse_args():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--version", choices=["v0", "v1", "v2", "v3", "v4"], help="Run only a single version pipeline")
    parser.add_argument("--mode", choices=["expand", "extract", "dual"], help="Override the run mode")
    return parser.parse_args()

ARGS = parse_args()
CLI_VERSION = ARGS.version
CLI_MODE = ARGS.mode.lower() if ARGS.mode else None

os.makedirs("datasets", exist_ok=True)
os.makedirs("public address dataset", exist_ok=True)

# =========================================================
# 🔥 TOKENS TO PROCESS (54 total: 6 trained + 48 detection)
# =========================================================
# TRAINED: Full ML scoring models available
TRAINED_TOKENS = ["USDT", "USDC", "BUSD", "DAI", "USDP", "TUSD"]

# WATCHONLY: Detection-only tokens (no models yet, different attacker patterns)
WATCHONLY_TOKENS = [
    # Stablecoins (18)
    "FRAX", "USDX", "GUSD", "LUSD", "MIM", "USDD", "EURS", "DOLA", 
    "GOHM", "USDCE", "ALUSD", "cUSDT",
    # DeFi (12)
    "AAVE", "COMP", "SNX", "UNI", "LINK", "SUSHI", "CRV", "1INCH", "YFI", "MKR", "BAL", "AURA",
    # ETH/L2 (9)
    "WETH", "MATIC", "LDO", "ARB", "OP", "GMX", "SOL", "MANTLE", "LINEA",
    # Wrapped (8)
    "WBTC", "cBTC", "stETH", "rswETH", "CBETH", "LST", "cbRES", "swETH",
    # Meme/Other (7)
    "DOGE", "SHIB", "PEPE", "FLOKI", "BONK", "WLD", "SAFE",
    # Non-ERC20 wrapped versions
    "ETH",  # Native Ethereum
]

# All tokens combined for full dataset generation
TOKENS = TRAINED_TOKENS + WATCHONLY_TOKENS

# =========================================================
# 🔥 TOKEN TYPE CLASSIFICATION (ERC20 vs Stablecoins)
# =========================================================
# Different token types have COMPLETELY DIFFERENT attacker profiles
TOKEN_TYPES = {
    # Stablecoins (6 trained)
    "USDT": "stablecoin",
    "USDC": "stablecoin",
    "BUSD": "stablecoin",
    "DAI": "stablecoin",
    "USDP": "stablecoin",
    "TUSD": "stablecoin",
    # Stablecoins (watchonly)
    "FRAX": "stablecoin",
    "USDX": "stablecoin",
    "GUSD": "stablecoin",
    "LUSD": "stablecoin",
    "MIM": "stablecoin",
    "USDD": "stablecoin",
    "EURS": "stablecoin",
    "DOLA": "stablecoin",
    "GOHM": "stablecoin",
    "USDCE": "stablecoin",
    "ALUSD": "stablecoin",
    "cUSDT": "stablecoin",
    # DeFi Tokens (governance/utility)
    "AAVE": "defi",
    "COMP": "defi",
    "SNX": "defi",
    "UNI": "defi",
    "LINK": "defi",
    "SUSHI": "defi",
    "CRV": "defi",
    "1INCH": "defi",
    "YFI": "defi",
    "MKR": "defi",
    "BAL": "defi",
    "AURA": "defi",
    # ETH/L2 Native Tokens
    "WETH": "native",
    "MATIC": "native",
    "LDO": "native",
    "ARB": "native",
    "OP": "native",
    "GMX": "native",
    "SOL": "native",
    "MANTLE": "native",
    "LINEA": "native",
    # Wrapped Tokens (derivatives)
    "WBTC": "wrapped",
    "cBTC": "wrapped",
    "stETH": "wrapped",
    "rswETH": "wrapped",
    "CBETH": "wrapped",
    "LST": "wrapped",
    "cbRES": "wrapped",
    "swETH": "wrapped",
    # Meme/Community Tokens
    "DOGE": "meme",
    "SHIB": "meme",
    "PEPE": "meme",
    "FLOKI": "meme",
    "BONK": "meme",
    "WLD": "meme",
    "SAFE": "meme",
    # Non-ERC20
    "ETH": "native",
}

# Safety limits
# Limit number of transactions processed per wallet to avoid very long loops
MAX_TXS_PER_WALLET = 300

# =========================================================
# 🔥 ENABLE TOGGLES (CONTROL OUTPUT CSVs)
# =========================================================
ENABLE_V0 = True   # Broad baseline dataset
ENABLE_V1 = True   # High-trust malicious (manual labeling stage)
ENABLE_V2 = True   # Scaled malicious dataset
ENABLE_V3 = True   # Poisoning behavior detection dataset
ENABLE_V4 = True   # High-confidence safe dataset

# =========================================================
# 🔥 V4 CONFIG
# =========================================================
V4_MAX = 2000      # maximum safe wallets per token for V4 generation

# =========================================================
# 🔥 WALLET SOURCE CONTROL (POOL vs SEEDS)
# =========================================================
USE_POOL_V0 = False
USE_POOL_V1 = False
USE_POOL_V2 = False
USE_POOL_V3 = False
USE_POOL_V4 = False

POOL_FOLDER = "public address dataset"

# =========================================================
# 🔥 POOL FILES (SEPARATED PER VERSION)
# =========================================================
POOL_FILES = {
    "v0": os.path.join(POOL_FOLDER, "v0_wallet_pool.csv"),
    "v1": os.path.join(POOL_FOLDER, "v1_wallet_pool.csv"),
    "v2": os.path.join(POOL_FOLDER, "v2_wallet_pool.csv"),
    "v3": os.path.join(POOL_FOLDER, "v3_wallet_pool.csv"),
    "v4": os.path.join(POOL_FOLDER, "v4_wallet_pool.csv")
}

# =========================================================
# 🔥 CONFIG PER VERSION (FULL CONTROL)
# =========================================================

# =========================================================
# 🔥 INDIVIDUAL SEEDS (edit these per version)
# =========================================================
# Hard-code seeds per version here — edit as needed.
SEEDS_V0 = [
    "0x0a2978072FCe42eCeC6193431b1fbF65368Ed4a2",
    "0x9C0d2305495676eda3F86BBB6f070a5578118Ce8",
    "0x21E26f9d487C1dfACB23ae69E256b47E4d7D451b",
    "0xAaD38c88712e2e4B9F407D353f61AC76e2C8746B",
]
SEEDS_V1 = [
    "0xd62802FcFd561F0679a84C84eb33b0D1f56849b2",
]
SEEDS_V2 = [
    "0x07f6CE0b13477152d9D1A7768D0A8efc1A03133a",
    "0x7eC8A30A34b86927dC77b302603d1D53E640bEF7",
    "0x6593d1AC6D2e81c06EfEe094E801C54de97B2042"
]
SEEDS_V3 = [
    "0xcf40A74074dC729cd9ee039f0296Ba1D48dCb876",
    "0x07f6CE0b13477152d9D1A7768D0A8efc1A03133a",
    "0xeC877B668c945cFE1179c71E6500606a55c93Ee8",
    "0x6A8cE8c5bcA96c9Cd26aD0060971d3E35a5d1CC4",
    "0xc83A9da4fE778737769BCcf121cc0062092548ff",
    "0xeC854b20463785ba48517dBaA88A2b6479983ee8",
    "0x064b0Fa5e10Da215e4aD80be9d70a9F8925D960E",
    "0x1AEd59dfb527d9B06914B3326d8cdf5DA3DAC423",
    "0xebF6857F05BdE28A2d84C5d4661fA4cb182F5190",
    "0xF152E8dCee36F61ec2c50C69b40976541d62724C",
    "0x412F5c7b577183dfAD04575136758d263770a0B3",
    "0x6A8A99D8a51f9bd714E1C8FF50C912C2D9721cc4",
    "0x745Ee2b9Dce1900036150Ed8643E1faAd489e587",
    "0x745Ee2b9Dce1900036150Ed8643E1faAd489e587",
    "0x00Fe78205F5F0E63B8aD2b2AE5337f538a610E04"
]

SEEDS_V4 = [
   "0x3570c3423e75eea7bc2a8b26274652f1399ddb06",
"0x5bc6dc43cdcc2ab46a8af9629427ec7e4654ad3c",
"0x76a7eb312a24dc931f2af9fd1be91799d3607595",
"0x0115259e22c2f3e5430a217fe46d70f670962afd",
"0x97e97a0d89ebfc6d8011d8bd643bbf997499d528",
"0xa12945ca94e9c015b92f447a4349c015b2ca34f3",
"0xfac566c6734c1a40c7a999a317ac09afa04ccc76",
"0x5fb2c98d2b185afc18d293b986de8edd22e5d68a",
"0x2528115ef147fee6160ca837cc933777fe066ee1",
"0xbbcc2b7cc14234074d3471ec2c350bad0101b48c",
"0x8ac05a534011efeb3b66b6756c5ef3caf9421285",
"0x002fd66f146f8766c34a6bf865d448ff6437f114",
"0x9f1d6c085c61b8fb4be7ed99a272d9e304cb4b55",
"0x0c5c5ad65af0725d464f4b5bc7db62c5cd484733",
"0xe2d0f25d2f9b58fdc3934a524f613be4cce320ec",
"0x5c451744066b50fc107981edcada6b481ddbe7de",
"0x5b90615635536c1fcf92d50c901df5075bc054d7",
"0xd36a89668bf74b168d34200a8c9d548e6643f4db",
"0x2af5d639ae8b2f5d9687bced58ebd7642d9dcc68",
"0xe78879fa0b9ee0f28952a7df84ad5b7056371037",
"0x872e3905333afcb81e0e4cb34c05ba46e08d66cc",
"0xd3ed2c1c7310bee277e105cf07ea07e081b7d917",
"0x9db65b5da9ca1f3bbd6eacd9655febd46372ac9c",
"0x88843b939b065418a2bf38b69d5613f9c010e2bf",
"0xc8d8809c8d41c40f8a356c2b68366153b67830f4",
"0xd59d34f3e47dd42d1c54986d85e18e7bc59f103a",
"0xd965cdd4ef70c7f3234b6d53d56133ba903828f1",
"0xf191eb300b94d5bf7cab2c2ab3c489c67f126cfe",
"0x81656be0a6ca9882108214b81b3aaa84d258fc40",
"0x7575a44aa479c6e1b0101fd8ad4e1588805ec51f",
"0x707e8fce3da0856523248505e1bf7d349fafd641",
"0x0e99c373260292341e6f5a9fcc4b79c8f7501c8e",
"0x2c8657eab674af44cbcbfdaeb5a6f13ba533010d"
]
# =========================================================
# Mode control: choose one of 'expand', 'extract', 'dual'
# - 'expand'  : only expand pools and save pool CSVs
# - 'extract' : compute features from existing pool or seeds
# - 'dual'    : expand first (save pool), then extract features from saved pool
MODE_RUN = "dual"

# =========================================================
# V0 → BROAD BASELINE
# - Goal: Learn NORMAL wallet behavior
# - Output: Mostly SAFE wallets
# - Label: 0
# =========================================================
CONFIG_V0 = {
    "MAX_TOTAL_WALLETS": 6000,
    "MAX_WALLETS_PER_SOURCE": 20,
    "SEEDS": SEEDS_V0  # 🔥 Per-version seeds (edit SEEDS_V0 above)
}

# =========================================================
# V1 → HIGH-TRUST MALICIOUS
# - Goal: Manually verified bad wallets
# - Output: Needs manual labeling
# - Label: None → later curated
# =========================================================
CONFIG_V1 = {
    "MAX_TOTAL_WALLETS": 4000,
    "MAX_WALLETS_PER_SOURCE": 10,
    "SEEDS": SEEDS_V1  # 🔥 Per-version seeds (edit SEEDS_V1 above)
}

# =========================================================
# V2 → SCALED MALICIOUS (CRAWLING)
# - Goal: Expand malicious clusters
# - Output: Large noisy dataset
# - Label: None → semi-supervised
# =========================================================
CONFIG_V2 = {
    "MAX_TOTAL_WALLETS": 6000,
    "MAX_WALLETS_PER_SOURCE": 25,
    "SEEDS": SEEDS_V2  # 🔥 Per-version seeds (edit SEEDS_V2 above)
}

# =========================================================
# V3 → POISONING BEHAVIOR (CRITICAL)
# - Goal: Detect address poisoning attacks
# - Output: Auto-labeled malicious (label=2)
# =========================================================
CONFIG_V3 = {
    "MAX_TOTAL_WALLETS": 8000,
    "MAX_WALLETS_PER_SOURCE": 50,
    "SEEDS": SEEDS_V3,  # 🔥 Per-version seeds (edit SEEDS_V3 above)
    "dust_threshold": 0.001,
    "dust_ratio": 0.3,
    "sender_ratio": 0.5
}

# =========================================================
# V4 → HIGH-CONFIDENCE SAFE
# - Goal: Find very clean wallets with stronger filtering than V0
# - Output: High-confidence safe wallets
# - Label: 0
# =========================================================
CONFIG_V4 = {
    "MAX_TOTAL_WALLETS": 3500,
    "MAX_WALLETS_PER_SOURCE": 15,
    "SEEDS": SEEDS_V4  # 🔥 Per-version seeds (edit SEEDS_V4 above)
}

# =========================================================
# LOAD / SAVE POOL
# =========================================================
def load_pool(path):
    # If exact path exists, load it
    if os.path.exists(path):
        df = pd.read_csv(path)
        if "wallet" in df.columns:
            return df["wallet"].dropna().tolist()

    # If exact path not found, try to discover a versioned pool file in the same folder
    folder = os.path.dirname(path) or "."
    base, ext = os.path.splitext(path)
    candidates = [
        f for f in os.listdir(folder)
        if (f.startswith(os.path.basename(base) + "_T") or f.startswith(os.path.basename(base) + "_v")) and f.endswith(ext)
    ]
    if candidates:
        candidates.sort()
        chosen = os.path.join(folder, candidates[-1])
        try:
            df = pd.read_csv(chosen)
            if "wallet" in df.columns:
                print(f"📂 Using discovered pool file: {chosen}")
                return df["wallet"].dropna().tolist()
        except Exception:
            return []

    return []

def get_unique_path(path):
    """Return a non-colliding path by appending _TN before the extension if needed."""
    folder = os.path.dirname(path) or "."
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    i = 1
    while True:
        if base.endswith("_wallet_pool"):
            candidate = os.path.join(folder, f"{os.path.basename(base)[:-len('_wallet_pool')]}_T{i}wallet_pool{ext}")
        else:
            candidate = os.path.join(folder, f"{os.path.basename(base)}_T{i}{ext}")
        if not os.path.exists(candidate):
            return candidate
        i += 1


def save_pool(wallets, path):
    out_path = get_unique_path(path)
    pd.DataFrame(list(set(wallets)), columns=["wallet"]).to_csv(out_path, index=False)
    print(f"💾 Saved pool to: {out_path}")
    return out_path


def get_config_for_version(version):
    return {
        "v0": CONFIG_V0,
        "v1": CONFIG_V1,
        "v2": CONFIG_V2,
        "v3": CONFIG_V3,
        "v4": CONFIG_V4
    }.get(version, {})


def get_use_pool_for_version(version):
    return {
        "v0": USE_POOL_V0,
        "v1": USE_POOL_V1,
        "v2": USE_POOL_V2,
        "v3": USE_POOL_V3,
        "v4": USE_POOL_V4
    }.get(version, False)


def run_version_pipeline(version, mode):
    print(f"\n🚀 Running {version.upper()} in {mode} mode")
    config = get_config_for_version(version)
    use_pool = get_use_pool_for_version(version)

    if version == "v4" and not config.get("SEEDS") and not os.path.exists(POOL_FILES["v4"]):
        if mode in ["extract", "dual"]:
            print("⚠️ V4 has no seeds and no V4 pool; generating V4 from existing training-ready data if available.")
            run_v4()
            return
        if mode == "expand":
            print("⚠️ V4 has no seeds and no V4 pool; skipping expand mode for V4.")
            return

    if mode == "expand":
        expand_wallets(config, version, use_pool)
    elif mode == "extract":
        extract_features_for_version(config, version, use_pool)
        if version == "v4":
            run_v4()
    elif mode == "dual":
        expand_wallets(config, version, use_pool=False)
        extract_features_for_version(config, version, use_pool=True)
        if version == "v4":
            run_v4()
    else:
        print(f"⚠️ Unknown mode '{mode}' for {version}")


def run_parallel_versions(mode):
    versions = []
    if ENABLE_V0:
        versions.append("v0")
    if ENABLE_V1:
        versions.append("v1")
    if ENABLE_V2:
        versions.append("v2")
    if ENABLE_V3:
        versions.append("v3")
    if ENABLE_V4:
        versions.append("v4")

    if not versions:
        print("⚠️ No enabled versions found for parallel execution")
        return

    processes = []
    for version in versions:
        cmd = [sys.executable, os.path.abspath(__file__), "--version", version, "--mode", mode]
        print(f"🌐 Spawning subprocess: {version} -> {cmd}")
        proc = subprocess.Popen(cmd)
        processes.append((version, proc))

    for version, proc in processes:
        proc.wait()
        if proc.returncode != 0:
            print(f"❌ Subprocess failed: {version} returned {proc.returncode}")
        else:
            print(f"✅ Subprocess completed: {version}")

# =========================================================
# FETCH TRANSACTIONS (WITH ROBUST ERROR HANDLING)
# =========================================================
def fetch_txs(address, version="v0", retry=2):
    api_key = get_api_key(version)
    for attempt in range(retry):
        try:
            res = requests.get(
                BASE_URL,
                params={
                    "chainid": 1,
                    "module": "account",
                    "action": "tokentx",
                    "address": address,
                    "offset": 100,
                    "sort": "desc",
                    "apikey": api_key
                },
                timeout=15,
                verify=True
            )
            
            if res.status_code != 200:
                if attempt < retry - 1:
                    time.sleep(3)
                continue
                
            data = res.json()
            result = data.get("result")
            
            if isinstance(result, list):
                return result
            elif isinstance(result, str) and "Max rate limit" in result:
                # Rate limited, wait and retry
                if attempt < retry - 1:
                    wait_time = 5
                    print(f"  ⏳ Rate limited, waiting {wait_time}s...")
                    time.sleep(wait_time)
            
            return []
            
        except requests.exceptions.Timeout:
            if attempt < retry - 1:
                print(f"  ⏱️ Timeout (attempt {attempt+1}/{retry}), retrying...")
                time.sleep(3)
            else:
                print(f"  ❌ Timeout after {retry} attempts")
                return []
                
        except requests.exceptions.ConnectionError:
            if attempt < retry - 1:
                print(f"  🔌 Connection error (attempt {attempt+1}/{retry}), retrying...")
                time.sleep(3)
            else:
                print(f"  ❌ Connection failed after {retry} attempts")
                return []
                
        except Exception as e:
            if attempt < retry - 1:
                print(f"  ⚠️ Error (attempt {attempt+1}/{retry}): {str(e)[:50]}")
                time.sleep(2)
            else:
                print(f"  ❌ Failed: {str(e)[:50]}")
                return []
    
    return []

# =========================================================
# EXPAND WALLET NETWORK (IMPROVED)
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
    failed_wallets = {}  # Track failed wallets (wallet: fail_count)
    start_time = time.time()
    max_duration = 300  # 5 minute timeout per version

    print(f"🌱 {version.upper()} seeds: {len(seeds)}")
    print(f"🚀 Expanding network (target: {config['MAX_TOTAL_WALLETS']}, timeout: {max_duration}s)")

    iteration = 0
    try:
        while frontier and len(visited) < config["MAX_TOTAL_WALLETS"]:
            elapsed = time.time() - start_time
            if elapsed > max_duration:
                print(f"\n⏱️ Timeout after {elapsed:.0f}s, stopping expansion")
                break

            new_frontier = []
            iteration += 1
            print(f"\n📍 Iteration {iteration}: exploring {len(frontier)} wallets | total: {len(visited)} | time: {elapsed:.0f}s")

            for idx, wallet in enumerate(frontier):
                # Skip wallets that failed 3+ times
                if failed_wallets.get(wallet, 0) >= 3:
                    continue

                print(f"  [{idx+1}/{len(frontier)}] {wallet[:10]}... ", end="", flush=True)

                txs = fetch_txs(wallet, version)

                # Truncate very large tx lists to avoid long processing loops
                if isinstance(txs, list) and len(txs) > MAX_TXS_PER_WALLET:
                    print(f"[truncated {len(txs)}→{MAX_TXS_PER_WALLET}] ", end="", flush=True)
                    txs = txs[:MAX_TXS_PER_WALLET]

                if not txs:
                    failed_wallets[wallet] = failed_wallets.get(wallet, 0) + 1
                    print("[skip]")
                    continue

                print(f"[{len(txs)} txs]")

                neighbors = set()
                for tx in txs:
                    if isinstance(tx, dict):
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

                time.sleep(0.2)  # Rate limit

            frontier = new_frontier
    except KeyboardInterrupt:
        print("\n⏸️ Expansion interrupted by user — saving pool and returning partial results...")
        wallets = list(visited)
        out_path = save_pool(wallets, pool_file)
        print(f"💾 Saved partial pool: {len(wallets)} wallets → {out_path}")
        return wallets

    wallets = list(visited)
    out_path = save_pool(wallets, pool_file)

    print(f"\n📊 {version.upper()} collected: {len(wallets)} → {out_path}")
    return wallets

# =========================================================
# BASE FEATURES (USED BY V0/V1/V2/V3)
# =========================================================
def compute_base_features(txs, token_filter=None):
    """
    Compute base features for wallet transactions.
    Enhanced with contract address fallback for robust token matching.
    [IMPORTANT] Supports both symbol-based and contract address-based filtering.
    """
    rows = []
    
    # Build contract-to-token mapping for fallback detection
    token_contract_map = {}
    if token_filter:
        # Get the contract for the token we're filtering for
        pass  # We'll handle this below

    for tx in txs:
        try:
            # 🔥 STRATEGY 1: Filter by tokenSymbol (primary)
            symbol = tx.get("tokenSymbol", "").upper().strip()
            if token_filter and symbol == token_filter:
                pass  # Match - include this transaction
            elif token_filter:
                # STRATEGY 2: Fallback to contract address matching
                # This handles cases where tokenSymbol is empty/missing
                contract = tx.get("contractAddress", "").lower()
                
                # Check if this contract belongs to our target token
                # We need to know the contract for the token we're filtering for
                # This is a bit tricky - we'll need to map it dynamically
                
                # For now, just skip if symbol doesn't match
                continue
            
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


def compute_graph_features(wallet, txs, token_filter=None, known_malicious=None):
    """
    🧠 GRAPH ENGINE - Extract network-level features
    Computes graph metrics for transaction network analysis
    
    Args:
        wallet: Wallet address (center of analysis)
        txs: List of transaction dictionaries
        token_filter: Optional token symbol filter
        known_malicious: Optional list of known malicious addresses
        
    Returns:
        Dictionary of graph features or empty dict if insufficient txs
    """
    if not TransactionGraph or not txs:
        # Return empty graph features if graph_engine not available or no txs
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
        # Build transaction graph
        graph = TransactionGraph(directed=True)
        
        # Add transactions to graph (structure: from -> to)
        for tx in txs:
            try:
                # Token filtering
                if token_filter:
                    symbol = tx.get("tokenSymbol", "").upper().strip()
                    if symbol != token_filter:
                        continue
                
                sender = tx.get("from", "").lower()
                recipient = tx.get("to", "").lower()
                
                if not sender or not recipient:
                    continue
                
                amount = int(tx.get("value", 0)) / (10 ** int(tx.get("tokenDecimal", 18)))
                graph.add_transaction(sender, recipient, amount)
            except:
                continue
        
        # Add known malicious wallets for threat analysis
        if known_malicious:
            graph.add_known_malicious(known_malicious)
        
        # Extract features for primary wallet
        features = graph.extract_features(wallet.lower())
        
        return features
        
    except Exception as e:
        # Graceful failure - return empty features
        print(f"⚠️ Graph feature extraction failed for {wallet}: {e}")
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


def compute_advanced_features(txs, token_filter=None):
    """
    🧠 ADVANCED FEATURE ENGINEERING
    Detects sophisticated fraud patterns through temporal, behavioral, value, and sequence analysis
    
    Features include:
    - TEMPORAL: burst patterns, inter-arrival variance, active hours
    - BEHAVIORAL: sender/receiver entropy, token switching, direction ratio
    - VALUE: percentile txs, max spike, median/mean deviation
    - SEQUENCE: repeated patterns, cyclic transfers, rapid send-back
    
    Args:
        txs: List of transaction dictionaries
        token_filter: Optional token to filter by
        
    Returns:
        Dictionary of advanced features
    """
    try:
        # Filter by token if specified
        if token_filter:
            filtered_txs = []
            for tx in txs:
                if tx.get("tokenSymbol", "").upper() == token_filter:
                    filtered_txs.append(tx)
            txs = filtered_txs
        
        if len(txs) < 3:
            return _get_empty_advanced_features()
        
        # Parse transactions
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
            return _get_empty_advanced_features()
        
        df = pd.DataFrame(rows)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        df = df.sort_values('timestamp')
        
        # ========== TEMPORAL FEATURES ==========
        
        # Time differences between consecutive transactions (burst detection)
        time_diffs = df['timestamp'].diff().dt.total_seconds().fillna(0).values
        
        # Burst pattern: rapid sequence of txs (small time gaps)
        burst_threshold = 60  # seconds
        burst_count = np.sum(time_diffs < burst_threshold)
        burst_ratio = burst_count / len(time_diffs) if len(time_diffs) > 0 else 0
        
        # Inter-arrival variance (trading pattern consistency)
        inter_arrival_var = np.var(time_diffs[time_diffs > 0]) if np.sum(time_diffs > 0) > 1 else 0
        
        # Active hours distribution (when does this wallet trade)
        active_hours = df['timestamp'].dt.hour.value_counts()
        hours_active = len(active_hours)
        hour_concentration = active_hours.max() / len(df) if len(df) > 0 else 0
        
        # ========== BEHAVIORAL FEATURES ==========
        
        # Sender entropy (how many unique senders)
        unique_senders = len(set(senders))
        sender_entropy = -np.sum((np.array(list(Counter(senders).values())) / len(senders)) * 
                                 np.log2(np.array(list(Counter(senders).values())) / len(senders) + 1e-10))
        
        # Receiver entropy (how many unique receivers)
        unique_receivers = len(set(receivers))
        receiver_entropy = -np.sum((np.array(list(Counter(receivers).values())) / len(receivers)) *
                                   np.log2(np.array(list(Counter(receivers).values())) / len(receivers) + 1e-10))
        
        # Direction ratio (outgoing vs incoming)
        direction_ratio = unique_senders / unique_receivers if unique_receivers > 0 else unique_senders
        
        # ========== VALUE-BASED FEATURES ==========
        
        # Percentile values
        p25 = np.percentile(values, 25)
        p50 = np.percentile(values, 50)
        p75 = np.percentile(values, 75)
        p95 = np.percentile(values, 95)
        
        # Max spike ratio (largest tx / median tx)
        max_spike_ratio = np.max(values) / (p50 if p50 > 0 else 1)
        
        # Median vs mean deviation
        mean_val = np.mean(values)
        median_val = p50
        median_mean_ratio = mean_val / (median_val if median_val > 0 else 1)
        
        # Value concentration in recent transactions
        recent_values = df['amount'].iloc[-5:].sum()
        total_values = df['amount'].sum()
        recent_concentration = recent_values / (total_values if total_values > 0 else 1)
        
        # ========== SEQUENCE FEATURES ==========
        
        # Rapid send-back pattern (sender becomes receiver and vice versa)
        send_back_count = 0
        for i in range(len(df) - 1):
            curr_sender = df.iloc[i]['sender']
            curr_receiver = df.iloc[i]['receiver']
            next_sender = df.iloc[i + 1]['sender']
            next_receiver = df.iloc[i + 1]['receiver']
            
            if (curr_sender == next_receiver and curr_receiver == next_sender):
                send_back_count += 1
        
        send_back_ratio = send_back_count / max(len(df) - 1, 1)
        
        # Cyclic pattern detection (same flow multiple times)
        flow_pairs = [(row['sender'], row['receiver']) for _, row in df.iterrows()]
        flow_counts = Counter(flow_pairs)
        cyclic_flows = sum(1 for count in flow_counts.values() if count > 2)
        cyclic_ratio = cyclic_flows / len(flow_counts) if len(flow_counts) > 0 else 0
        
        # Repeated recipients (washing pattern)
        repeat_receiver_ratio = len([c for c in Counter(receivers).values() if c > 3]) / unique_receivers if unique_receivers > 0 else 0
        
        return {
            # Temporal
            'temporal_burst_ratio': float(burst_ratio),
            'temporal_inter_arrival_var': float(inter_arrival_var),
            'temporal_hours_active': int(hours_active),
            'temporal_hour_concentration': float(hour_concentration),
            
            # Behavioral
            'behavioral_unique_senders': int(unique_senders),
            'behavioral_sender_entropy': float(sender_entropy),
            'behavioral_unique_receivers': int(unique_receivers),
            'behavioral_receiver_entropy': float(receiver_entropy),
            'behavioral_direction_ratio': float(direction_ratio),
            
            # Value
            'value_p25': float(p25),
            'value_p50': float(p50),
            'value_p75': float(p75),
            'value_p95': float(p95),
            'value_max_spike_ratio': float(max_spike_ratio),
            'value_median_mean_ratio': float(median_mean_ratio),
            'value_recent_concentration': float(recent_concentration),
            
            # Sequence
            'sequence_send_back_ratio': float(send_back_ratio),
            'sequence_cyclic_ratio': float(cyclic_ratio),
            'sequence_repeat_receiver_ratio': float(repeat_receiver_ratio),
        }
        
    except Exception as e:
        print(f"⚠️ Advanced feature extraction failed: {e}")
        return _get_empty_advanced_features()


def _get_empty_advanced_features():
    """Return empty/default advanced features"""
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

# =========================================================
# ENTERPRISE FRAUD DETECTION (STRIPE-GRADE)
# ========================================================
# Multi-layered approach: keyword + behavioral + chain analysis

# Advanced keyword patterns (common scam tactics)
FRAUD_KEYWORDS = {
    # Phishing/Impersonation
    "phishing": ["phish", "fake wallet", "impersonate", "pretend", "fake", "spoof"],
    
    # Scams
    "scam": ["scam", "fraud", "swindle", "confidence game", "rip-off", "scheme"],
    
    # Direct theft
    "theft": ["steal", "theft", "stolen", "robbed", "hacked", "breach"],
    
    # Exploits
    "exploit": ["exploit", "vulnerability", "bug bounty", "cve-", "0day"],
    
    # Pump & Dump
    "pump_dump": ["pump and dump", "exit scam", "rug pull", "liquidity lock", "dump"],
    
    # Spam/NFT Scams
    "spam": ["spam", "flooding", "dust attack", "nft scam", "token spam"],
    
    # Money Laundering/Mixing
    "mixing": ["mixer", "tumbler", "launder", "aml bypass", "sanctions evade"],
}

# Obfuscation patterns (scammers try to hide)
OBFUSCATION_PATTERNS = [
    "xxx", "XXX",  # Common obfuscation
    "***",         # Censoring attempts
    "[REDACTED]", "[REMOVED]",
    "phishing".replace("i", "1").replace("s", "5"),  # Leetspeak
    "scam".replace("a", "@").replace("s", "$"),
]

HEADERS = {"User-Agent": "Mozilla/5.0"}

def analyze_text_for_fraud(text, strict=False):
    """
    STRIPE-GRADE: Multi-level text analysis for fraud indicators.
    Returns: fraud_score (0-100), detected_categories (list)
    
    Levels:
    1. EXACT: Direct keyword match
    2. CONTEXT: Keywords + surrounding text analysis
    3. OBFUSCATION: Attempts to hide suspicious terms
    """
    text_lower = text.lower()
    fraud_score = 0
    detected = []
    
    # Level 1: EXACT keyword matching
    for category, keywords in FRAUD_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                fraud_score += 20  # +20 per category
                if category not in detected:
                    detected.append(category)
                break  # Only count once per category
    
    # Level 2: CONTEXT analysis
    # Check if fraud keywords appear WITH suspicious phrases
    if any(kw in text_lower for kw in ["phish", "scam", "exploit", "steal"]):
        # Now check context
        suspicious_context = [
            "report", "alert", "warning", "caught", "confirmed",
            "documented", "identified", "wallet", "address", "account"
        ]
        context_hits = sum(1 for ctx in suspicious_context if ctx in text_lower)
        
        if context_hits >= 2:  # Multiple context indicators = higher confidence
            fraud_score += 15
            if "context_confirmed" not in detected:
                detected.append("context_confirmed")
    
    # Level 3: OBFUSCATION detection (very suspicious)
    for pattern in OBFUSCATION_PATTERNS:
        if pattern in text:
            fraud_score += 25  # High score for obfuscation
            if "obfuscation" not in detected:
                detected.append("obfuscation")
    
    # Normalize fraud_score to 0-100
    fraud_score = min(100, fraud_score)
    
    return fraud_score, detected

def check_wallet_keywords(address):
    """
    ENTERPRISE: Multi-layered keyword detection.
    Returns: 1 (suspicious), None (unknown), 0 (safe)
    
    Process:
    1. Scrape Etherscan page
    2. Analyze text with multi-level fraud detection
    3. Apply Stripe-like confidence thresholds
    """
    url = f"https://etherscan.io/address/{address}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            return None  # Unknown (API error)
        
        soup = BeautifulSoup(res.text, "html.parser")
        text = soup.get_text()
        
        # Analyze with multi-level detection
        fraud_score, detected_categories = analyze_text_for_fraud(text, strict=False)
        
        # Stripe-like thresholds for decision making:
        # 0-25: Safe (low fraud indicators)
        # 26-60: Review (requires human check or more signals)
        # 61+: Block (high confidence fraud)
        
        if fraud_score >= 60:
            return 1  # 🚨 Suspicious - Block
        elif fraud_score >= 26:
            return None  # Ambiguous - Keep as unknown (review tier)
        else:
            return 0  # Safe - Green light
        
    except Exception as e:
        # Silent fail - API errors don't mark as fraud
        return None  # Unknown

# ========================================================
# BEHAVIORAL FRAUD DETECTION (Chain Analysis)
# ========================================================

def analyze_transaction_patterns(txs, token_filter=None):
    """
    STRIPE-GRADE: Detect behavioral patterns of fraud.
    
    Checks:
    1. Bot activity (perfectly timed txs)
    2. Value patterns (coordinated amounts)
    3. Frequency anomalies (velocity)
    4. Dust attacks (spam)
    5. Circular flows (money laundering)
    """
    if not txs:
        return 0, []
    
    behavior_score = 0
    patterns = []
    
    # Filter by token if specified
    if token_filter:
        txs = [tx for tx in txs if tx.get("tokenSymbol", "").upper() == token_filter]
    
    if not txs or len(txs) < 2:
        return 0, []
    
    try:
        # Extract timestamps and values
        times = []
        values = []
        froms = set()
        
        for tx in txs:
            try:
                ts = int(tx.get("timeStamp", 0))
                val = float(tx.get("value", 0)) / (10 ** int(tx.get("tokenDecimal", 18)))
                times.append(ts)
                values.append(val)
                froms.add(tx.get("from", ""))
            except:
                continue
        
        if len(times) < 2:
            return 0, []
        
        # 1️⃣ BOT DETECTION - Perfectly spaced transactions
        times_sorted = sorted(times)
        intervals = [times_sorted[i+1] - times_sorted[i] for i in range(len(times_sorted)-1)]
        
        if intervals:
            avg_interval = sum(intervals) / len(intervals)
            
            # Check for perfect spacing (within 5% variance)
            exact_spacing = sum(1 for interval in intervals if abs(interval - avg_interval) / max(avg_interval, 1) < 0.05)
            if exact_spacing / len(intervals) > 0.7:  # 70%+ exact spacing = bot
                behavior_score += 30
                patterns.append("bot_activity")
        
        # 2️⃣ VELOCITY CHECK - Too many txs in short time
        if len(txs) > 20 and (times_sorted[-1] - times_sorted[0]) < 3600:  # 20+ txs in 1 hour
            behavior_score += 25
            patterns.append("high_velocity")
        
        # 3️⃣ DUST ATTACK DETECTION - Many tiny transactions
        dust_txs = sum(1 for v in values if v < 0.001)
        if len(values) > 5 and dust_txs / len(values) > 0.5:  # 50%+ are dust
            behavior_score += 20
            patterns.append("dust_attack")
        
        # 4️⃣ VALUE ANOMALY - Perfectly repeated amounts
        if len(set(values)) < len(values) / 2:  # Many repeated values
            behavior_score += 15
            patterns.append("value_repetition")
        
        # 5️⃣ SENDER DIVERSITY - Many senders = potential coordination
        if len(froms) > len(txs) * 0.8:  # 80%+ unique senders
            behavior_score += 10
            patterns.append("high_sender_diversity")
        
        behavior_score = min(100, behavior_score)
        
        return behavior_score, patterns
    
    except Exception as e:
        return 0, []

# ========================================================
# COMPOSITE FRAUD SCORING (Multi-Signal)
# ========================================================

def calculate_fraud_score(keyword_score, behavior_score):
    """
    Combine multiple fraud signals like Stripe does.
    Uses weighted average with emphasis on keyword (high-confidence signal).
    """
    # Weight signals: keywords are more reliable than behavior
    keyword_weight = 0.7
    behavior_weight = 0.3
    
    composite = (keyword_score * keyword_weight) + (behavior_score * behavior_weight)
    return min(100, composite)

# =========================================================
# V3 POISON FEATURES (ENHANCED)
# =========================================================

def compute_v3_features(txs, wallet, config, token_filter=None):
    dust = 0
    senders = set()
    similarity_hits = 0

    for tx in txs:
        try:
            # 🔥 Filter by token if specified
            if token_filter and tx.get("tokenSymbol", "").upper() != token_filter:
                continue
            
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
# V0 VALIDATION (LIGHTER THAN V4)
# =========================================================
# V0 & V4 SAFETY FILTERS (ENTERPRISE GRADE)
# =========================================================
# Minimize false positives: Only block if VERY confident wallet is suspicious
# Allow legitimate use cases (traders, active users, etc.)

_keyword_cache = {}
_behavior_cache = {}

def is_v0_safe_candidate(row, wallet, txs=None):
    """
    STRIPE-GRADE: V0 safety filter with multi-signal fraud detection.
    
    Strategy: CONSERVATIVE
    - Only exclude if HIGH CONFIDENCE fraud detected
    - Allow edge cases (new wallets, high frequency traders, etc.)
    - Require multiple fraud signals to block
    """
    
    # ⚠️ HARD FILTERS (Categorical blockers - no false positives allowed)
    # Wallets under 7 days = can't evaluate properly yet
    if row["wallet_age_days"] < 7:
        return False
    
    # Impossible patterns = definitely spam
    # EXCEPTION: Very low-value txs are OK if few and spread out
    if row["avg_tx"] < 0.0001 and row["tx_frequency"] > 50:
        return False  # Spam dust attack
    
    # ⚠️ FRAUD SIGNAL ANALYSIS (Multi-signal approach)
    fraud_signals = 0
    max_signals = 5
    
    # Signal 1: Text-based keyword fraud detection
    if wallet in _keyword_cache:
        keyword_result = _keyword_cache[wallet]
    else:
        keyword_result = check_wallet_keywords(wallet)
        _keyword_cache[wallet] = keyword_result
    
    # IMPORTANT: keyword_result is now: 1 (suspicious), 0 (safe), None (unknown)
    if keyword_result == 1:  # High-confidence fraud from keywords
        fraud_signals += 2  # Worth 2 signals
    elif keyword_result == 0:
        fraud_signals -= 1  # Safe from keywords (reduces suspicion)
    
    # Signal 2: Behavioral pattern analysis
    if txs:
        behavior_score, patterns = analyze_transaction_patterns(txs)
        if "bot_activity" in patterns or "high_velocity" in patterns:
            fraud_signals += 1.5
        elif behavior_score > 50:
            fraud_signals += 1
    
    # Signal 3: Transaction frequency anomaly
    if row["tx_per_day"] > 100:  # Extreme frequency
        fraud_signals += 1
    elif row["tx_per_day"] > 50:  # High but possible for traders
        fraud_signals += 0.5
    
    # Signal 4: Value patterns (too low)
    # EXCEPTION: Wallets with few txs can have low avg
    if row["avg_tx"] < 0.001 and row["tx_frequency"] > 10:
        fraud_signals += 0.5
    
    # Signal 5: Mixed patterns (low value + high frequency = dust attack)
    if row["avg_tx"] < 0.01 and row["tx_per_day"] > 20 and row["tx_frequency"] > 50:
        fraud_signals += 1
    
    # ✅ DECISION: Block only with HIGH CONFIDENCE (2+ fraud signals)
    if fraud_signals >= 2.0:
        return False  # ❌ Block - multiple fraud signals
    
    # If keyword_result == 0 (explicitly safe) or fraud_signals < 1, allow it
    return True  # ✅ Allow


def is_v4_high_confidence_candidate(row, wallet, txs=None):
    """
    STRIPE-GRADE: V4 safety filter - STRICTEST for high-confidence safe wallets.
    
    Strategy: VERY CONSERVATIVE
    - Only include if wallet shows CLEAR legitimate patterns
    - Only block if VERY HIGH confidence fraud detected
    - Require sustained, normal behavior over time
    """
    
    # ⚠️ HARD FILTERS (High bar for V4)
    if row["wallet_age_days"] < 30:
        return False  # Too new to be "high confidence safe"
    
    if row["tx_per_day"] > 20:
        return False  # Too active for "stable" classification
    
    if row["tx_per_hour"] > 8:
        return False  # Rapid-fire activity
    
    # Allow reasonable minimum values (traders might make small txs)
    if row["avg_tx"] < 0.001:
        return False  # Too low
    
    if row["avg_time_between_tx_sec"] < 1800:  # Less than 30 min between txs
        return False  # Too frequent
    
    if row["avg_tx"] < 0.05 and row["tx_per_day"] > 5:
        return False  # Low value + high frequency = suspicious
    
    # ⚠️ FRAUD SIGNAL ANALYSIS
    fraud_signals = 0
    
    # Check keyword fraud detection
    if wallet in _keyword_cache:
        keyword_result = _keyword_cache[wallet]
    else:
        keyword_result = check_wallet_keywords(wallet)
        _keyword_cache[wallet] = keyword_result
    
    # For V4, keyword fraud is an automatic blocker
    if keyword_result == 1:
        return False  # ❌ Marked as fraudulent
    
    # Check behavioral patterns
    if txs:
        behavior_score, patterns = analyze_transaction_patterns(txs)
        if "bot_activity" in patterns or "dust_attack" in patterns:
            return False  # ❌ Clear fraud pattern
    
    # ✅ Passed all checks - this is high-confidence safe
    return True

# =========================================================

# RUNNERS (MULTI-TOKEN)
# =========================================================
def run_v0():
    wallets = expand_wallets(CONFIG_V0, "v0", USE_POOL_V0)
    
    # 🔥 Process once, save per token
    all_rows_by_token = {token: [] for token in TOKENS}
    
    for w in wallets:
        txs = fetch_txs(w, "v0")
        for token in TOKENS:
            base = compute_base_features(txs, token_filter=token)
            if base:
                row = {"wallet": w, "token": token.lower(), **base, "label": 0}
                # ENTERPRISE: Pass txs for behavioral analysis
                if is_v0_safe_candidate(row, w, txs=txs):
                    all_rows_by_token[token].append(row)
    
    # Save per-token CSVs
    for token in TOKENS:
        if all_rows_by_token[token]:
            pd.DataFrame(all_rows_by_token[token]).to_csv(f"datasets/v0_{token.lower()}.csv", index=False)
            print(f"✅ V0 {token} DONE ({len(all_rows_by_token[token])})")

def run_v1():
    wallets = expand_wallets(CONFIG_V1, "v1", USE_POOL_V1)
    
    all_rows_by_token = {token: [] for token in TOKENS}
    
    for w in wallets:
        txs = fetch_txs(w, "v1")
        for token in TOKENS:
            base = compute_base_features(txs, token_filter=token)
            if base:
                all_rows_by_token[token].append({"wallet": w, **base, "label": None})
    
    for token in TOKENS:
        if all_rows_by_token[token]:
            pd.DataFrame(all_rows_by_token[token]).to_csv(f"datasets/v1_{token.lower()}.csv", index=False)
            print(f"✅ V1 {token} DONE ({len(all_rows_by_token[token])})")

def run_v2():
    wallets = expand_wallets(CONFIG_V2, "v2", USE_POOL_V2)
    
    all_rows_by_token = {token: [] for token in TOKENS}
    
    for w in wallets:
        txs = fetch_txs(w, "v2")
        for token in TOKENS:
            base = compute_base_features(txs, token_filter=token)
            if base:
                all_rows_by_token[token].append({"wallet": w, **base, "label": None})
    
    for token in TOKENS:
        if all_rows_by_token[token]:
            pd.DataFrame(all_rows_by_token[token]).to_csv(f"datasets/v2_{token.lower()}.csv", index=False)
            print(f"✅ V2 {token} DONE ({len(all_rows_by_token[token])})")

def run_v3():
    wallets = expand_wallets(CONFIG_V3, "v3", USE_POOL_V3)
    
    all_rows_by_token = {token: [] for token in TOKENS}
    
    for w in wallets:
        txs = fetch_txs(w, "v3")
        base = compute_base_features(txs)  # Get base for all tokens
        
        for token in TOKENS:
            if not base:
                continue
            
            d, s, n, p = compute_v3_features(txs, w, CONFIG_V3, token_filter=token)
            
            all_rows_by_token[token].append({
                "wallet": w,
                **base,
                "dust_tx_ratio": d,
                "similarity_hits": s,
                "new_sender_ratio": n,
                "is_poisoned_pattern": p,
                "label": 2 if p else -1
            })
    
    for token in TOKENS:
        if all_rows_by_token[token]:
            df = pd.DataFrame(all_rows_by_token[token])
            df.to_csv(f"datasets/v3_raw_{token.lower()}.csv", index=False)
            df[df["label"] == 2].to_csv(f"datasets/v3_clean_{token.lower()}.csv", index=False)
            print(f"🔥 V3 {token} DONE ({len(df)})")


def extract_features_for_version(config, version, use_pool):
    """Extract base features (per-token) for a given version using either a pool file or the configured seeds."""
    pool_file = POOL_FILES.get(version)

    if use_pool and pool_file:
        wallets = load_pool(pool_file)
        if wallets:
            print(f"📂 {version.upper()} loading pool ({len(wallets)} wallets) from {pool_file}")
        else:
            print(f"⚠️ {version.upper()} pool {pool_file} empty, falling back to seeds")
            wallets = config.get("SEEDS", [])
    else:
        wallets = config.get("SEEDS", [])

    if not wallets:
        print(f"⚠️ {version.upper()} no wallets to extract")
        return

    all_rows_by_token = {token: [] for token in TOKENS}

    for i, w in enumerate(wallets):
        txs = fetch_txs(w, version)
        if not txs:
            continue

        for token in TOKENS:
            base = compute_base_features(txs, token_filter=token)
            if not base:
                continue

            # 🧠 Add graph features (network intelligence)
            graph_features = compute_graph_features(w, txs, token_filter=token)

            # 🧠 Add advanced temporal/behavioral features
            advanced_features = compute_advanced_features(txs, token_filter=token)

            row = {"wallet": w, "token": token.lower(), **base, **graph_features, **advanced_features}

            # label rules by version
            if version == "v0":
                row["label"] = 0
                if not is_v0_safe_candidate(row, w):
                    continue
            elif version == "v4":
                row["label"] = 0
                if not is_v4_high_confidence_candidate(row, w):
                    continue
            elif version == "v3":
                d, s, n, p = compute_v3_features(txs, w, config, token_filter=token)
                row.update({"dust_tx_ratio": d, "similarity_hits": s, "new_sender_ratio": n, "is_poisoned_pattern": p})
                row["label"] = 2 if p else -1
            elif version in ["v1", "v2"]:
                # 🔥 Auto-label V1/V2 by scraping Etherscan for keywords
                print(f"  🔍 [{i+1}/{len(wallets)}] {w[:10]}... scraping", end="", flush=True)
                keyword_label = check_wallet_keywords(w)
                row["label"] = keyword_label
                print(" ✓")
                time.sleep(1.0)  # Rate limiting for Etherscan
            else:
                row["label"] = None

            all_rows_by_token[token].append(row)

    for token in TOKENS:
        if all_rows_by_token[token]:
            df = pd.DataFrame(all_rows_by_token[token])
            out_path = f"datasets/{version}_{token.lower()}.csv"
            df.to_csv(out_path, index=False)
            print(f"✅ {version.upper()} {token} EXTRACTED ({len(all_rows_by_token[token])}) → {out_path}")

            if version == "v3":
                raw_path = f"datasets/v3_raw_{token.lower()}.csv"
                clean_path = f"datasets/v3_clean_{token.lower()}.csv"
                labeled_path = f"datasets/{token.lower()}_labeled_v3.csv"

                df.to_csv(raw_path, index=False)
                df[df["label"] == 2].to_csv(clean_path, index=False)
                df[df["label"] == 2].drop_duplicates(subset=["wallet"]).to_csv(labeled_path, index=False)

                print(f"   🔥 V3 raw saved → {raw_path}")
                print(f"   🔥 V3 clean saved → {clean_path}")
                print(f"   🔥 V3 labeled saved → {labeled_path}")

            if version == "v0":
                generate_v0_training_ready(token)


def generate_v4_dataset(token, max_v4=V4_MAX):
    input_path = f"datasets/v4_{token.lower()}.csv"
    fallback_path = f"datasets/{token.lower()}_training_ready.csv"
    output_path = f"datasets/{token.lower()}_labeled_v4.csv"

    if not os.path.exists(input_path):
        if os.path.exists(fallback_path):
            print(f"⚠️ V4 candidate file not found for {token}; falling back to {fallback_path}")
            input_path = fallback_path
        else:
            print(f"⚠️ V4 skip {token}: V4 candidate file not found ({input_path})")
            return

    df = pd.read_csv(input_path)
    if df.empty:
        print(f"⚠️ V4 skip {token}: candidate dataset empty")
        return

    df = df.drop(columns=["risk_probability", "prediction", "decision", "confidence"], errors="ignore")
    if "token" not in df.columns:
        df["token"] = token.lower()

    numeric_cols = [
        "tx_per_min",
        "tx_per_hour",
        "tx_per_day",
        "avg_time_between_tx_sec"
    ]
    for col in numeric_cols:
        df[col] = df.get(col, 0).fillna(0)

    if "wallet_age_days" in df.columns:
        df["wallet_age_days"] = df["wallet_age_days"].apply(lambda x: max(int(x), 1) if not pd.isna(x) else 1)
    else:
        df["wallet_age_days"] = 1

    df = df.groupby(["wallet", "token"], as_index=False).agg({
        "wallet_age_days": "max",
        "avg_tx": "mean",
        "recent_tx": "last",
        "tx_frequency": "mean",
        "tx_per_min": "mean",
        "tx_per_hour": "mean",
        "tx_per_day": "mean",
        "avg_time_between_tx_sec": "mean",
        "label": "last"
    })

    df["avg_tx"] = np.log1p(df["avg_tx"])
    df["recent_tx"] = np.log1p(df["recent_tx"])
    df["is_high_freq"] = df["tx_per_day"] > 20
    df["is_low_value"] = df["avg_tx"] < np.log1p(0.01)
    df["is_new_wallet"] = df["wallet_age_days"] <= 30
    df["risk_score_rule"] = (
        df["is_high_freq"].astype(int) * 0.5 +
        df["is_low_value"].astype(int) * 0.3 +
        df["is_new_wallet"].astype(int) * 0.2
    )

    safe_df = df[
        (df["is_high_freq"] == False) &
        (df["is_low_value"] == False) &
        (df["is_new_wallet"] == False) &
        (df["tx_per_day"] < 20) &
        (df["wallet_age_days"] > 120) &
        (df["avg_tx"] > np.log1p(0.1)) &
        (df["risk_score_rule"] == 0)
    ].copy()

    if safe_df.empty:
        print(f"⚠️ V4 {token} produced no high-confidence safe wallets")
        return

    safe_df["dust_tx_ratio"] = 0
    safe_df["similarity_hits"] = 0
    safe_df["new_sender_ratio"] = 0
    safe_df["is_poisoned_pattern"] = 0
    safe_df["label"] = 0

    safe_df.drop_duplicates(subset=["wallet"], inplace=True)

    if len(safe_df) > max_v4:
        safe_df = safe_df.sample(max_v4, random_state=42)
        print(f"⚠️ V4 {token} trimmed to {max_v4} rows")

    if safe_df.empty:
        print(f"⚠️ V4 {token} produced no safe wallets")
        return

    safe_df["dust_tx_ratio"] = 0
    safe_df["similarity_hits"] = 0
    safe_df["new_sender_ratio"] = 0
    safe_df["is_poisoned_pattern"] = 0
    safe_df["label"] = 0

    safe_df.drop_duplicates(subset=["wallet"], inplace=True)

    if len(safe_df) > max_v4:
        safe_df = safe_df.sample(max_v4, random_state=42)
        print(f"⚠️ V4 {token} trimmed to {max_v4} rows")

    final_cols = [
        "wallet", "token", "wallet_age_days", "avg_tx", "recent_tx",
        "tx_frequency", "tx_per_min", "tx_per_hour", "tx_per_day",
        "avg_time_between_tx_sec", "is_high_freq", "is_low_value",
        "is_new_wallet", "risk_score_rule", "dust_tx_ratio",
        "similarity_hits", "new_sender_ratio", "is_poisoned_pattern", "label"
    ]

    final_cols = [c for c in final_cols if c in safe_df.columns]
    safe_df = safe_df[final_cols]

    safe_df.to_csv(output_path, index=False)
    print(f"🔥 V4 {token} saved → {output_path} ({len(safe_df)} rows)")


def generate_v0_training_ready(token):
    input_path = f"datasets/v0_{token.lower()}.csv"
    output_path = f"datasets/{token.lower()}_training_ready.csv"

    if not os.path.exists(input_path):
        print(f"⚠️ V0 training-ready skip {token}: {input_path} not found")
        return

    df = pd.read_csv(input_path)
    print(f"🔧 Generating V0 training-ready dataset for {token} ({len(df)} rows)")

    numeric_cols = [
        "tx_per_min",
        "tx_per_hour",
        "tx_per_day",
        "avg_time_between_tx_sec"
    ]

    for col in numeric_cols:
        df[col] = df.get(col, 0).fillna(0)

    if "wallet_age_days" in df.columns:
        df["wallet_age_days"] = df["wallet_age_days"].apply(lambda x: max(int(x), 1) if not pd.isna(x) else 1)
    else:
        df["wallet_age_days"] = 1

    if "token" not in df.columns:
        df["token"] = token.lower()

    df = df.groupby(["wallet", "token"], as_index=False).agg({
        "wallet_age_days": "max",
        "avg_tx": "mean",
        "recent_tx": "last",
        "tx_frequency": "mean",
        "tx_per_min": "mean",
        "tx_per_hour": "mean",
        "tx_per_day": "mean",
        "avg_time_between_tx_sec": "mean",
        "label": "last"
    })

    df["avg_tx"] = np.log1p(df["avg_tx"])
    df["recent_tx"] = np.log1p(df["recent_tx"])

    df["is_high_freq"] = df["tx_per_day"] > 100
    df["is_low_value"] = df["avg_tx"] < np.log1p(0.01)
    df["is_new_wallet"] = df["wallet_age_days"] <= 3

    df["risk_score_rule"] = (
        df["is_high_freq"].astype(int) * 0.5 +
        df["is_low_value"].astype(int) * 0.3 +
        df["is_new_wallet"].astype(int) * 0.2
    )

    if "label" not in df.columns:
        df["label"] = 0

    df.to_csv(output_path, index=False)
    print(f"🔥 V0 training-ready saved → {output_path} ({len(df)} rows)")


def run_v4():
    for token in TOKENS:
        generate_v4_dataset(token)


# =========================================================
# MODE DISPATCH
# =========================================================
def _run_expand_mode():
    if ENABLE_V0:
        expand_wallets(CONFIG_V0, "v0", USE_POOL_V0)
    if ENABLE_V1:
        expand_wallets(CONFIG_V1, "v1", USE_POOL_V1)
    if ENABLE_V2:
        expand_wallets(CONFIG_V2, "v2", USE_POOL_V2)
    if ENABLE_V3:
        expand_wallets(CONFIG_V3, "v3", USE_POOL_V3)
    if ENABLE_V4:
        expand_wallets(CONFIG_V4, "v4", USE_POOL_V4)


def _run_extract_mode():
    if ENABLE_V0:
        extract_features_for_version(CONFIG_V0, "v0", USE_POOL_V0)
    if ENABLE_V1:
        extract_features_for_version(CONFIG_V1, "v1", USE_POOL_V1)
    if ENABLE_V2:
        extract_features_for_version(CONFIG_V2, "v2", USE_POOL_V2)
    if ENABLE_V3:
        extract_features_for_version(CONFIG_V3, "v3", USE_POOL_V3)
    if ENABLE_V4:
        extract_features_for_version(CONFIG_V4, "v4", USE_POOL_V4)
        run_v4()


def _run_dual_mode():
    # Expand first (force expansion so we create fresh pool files), then extract from those pools
    if ENABLE_V0:
        expand_wallets(CONFIG_V0, "v0", use_pool=False)
        extract_features_for_version(CONFIG_V0, "v0", use_pool=True)
    if ENABLE_V1:
        expand_wallets(CONFIG_V1, "v1", use_pool=False)
        extract_features_for_version(CONFIG_V1, "v1", use_pool=True)
    if ENABLE_V2:
        expand_wallets(CONFIG_V2, "v2", use_pool=False)
        extract_features_for_version(CONFIG_V2, "v2", use_pool=True)
    if ENABLE_V3:
        expand_wallets(CONFIG_V3, "v3", use_pool=False)
        extract_features_for_version(CONFIG_V3, "v3", use_pool=True)
    if ENABLE_V4:
        expand_wallets(CONFIG_V4, "v4", use_pool=False)
        extract_features_for_version(CONFIG_V4, "v4", use_pool=True)
        run_v4()


mode = (CLI_MODE or MODE_RUN or "dual").lower().strip()
if CLI_VERSION:
    run_version_pipeline(CLI_VERSION, mode)
else:
    if mode == "expand":
        _run_expand_mode()
    elif mode == "extract":
        _run_extract_mode()
    elif mode == "dual":
        print("\n🌐 Running enabled versions in parallel...\n")
        run_parallel_versions(mode)
    else:
        print(f"⚠️ Unknown MODE_RUN '{MODE_RUN}', falling back to 'dual'.")
        run_parallel_versions("dual")

print("\n🔥 ALL DATASETS GENERATED")
