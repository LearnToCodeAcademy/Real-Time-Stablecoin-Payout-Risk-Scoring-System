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

API_KEY = "HP8KE56GFDIDIUCEGPAI9T5DCDYWIPYW4K"
BASE_URL = "https://api.etherscan.io/v2/api"

VERSION_API_KEYS = {
    "v0": "HP8KE56GFDIDIUCEGPAI9T5DCDYWIPYW4K",
    "v1": "HVJKPIBXH53KSZFNTWI9RTEN6EXT9UXK7R",
    "v2": "X3A2JP555Z4N1DYYYE4V8VFSUN9PZCGEUF",
    "v3": "QKB9WBBC6NYK1CCS3MGW6Q226A1WUSJ4KR",
    "v4": "HP8KE56GFDIDIUCEGPAI9T5DCDYWIPYW4K"
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
    "0x0a2978072FCe42eCeC6193431b1fbF65368Ed4a2"
]
SEEDS_V1 = [
    "0x3D0f22BF11636CC9cb129e2B261EEd35a487455C"
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
"0x3d0f22bf11636cc9cb129e2b261eed35a487455c",
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

# =========================================================
# ETHERSCAN KEYWORD SCRAPING (FOR V1/V2 AUTO-LABELING)
# =========================================================
KEYWORDS = ["phish", "scam", "spam", "hack", "exploit", "malicious"]
HEADERS = {"User-Agent": "Mozilla/5.0"}

def check_wallet_keywords(address):
    """Scrape Etherscan page for keywords. Return 1 if found, None if not found."""
    url = f"https://etherscan.io/address/{address}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            return None
        
        soup = BeautifulSoup(res.text, "html.parser")
        text = soup.get_text().lower()
        
        for kw in KEYWORDS:
            if kw in text:
                return 1  # Suspicious
        
        return None  # Unknown
    except Exception as e:
        print(f"  ⚠️ Scrape error: {str(e)[:40]}")
        return None

# =========================================================
# V3 POISON FEATURES
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
_keyword_cache = {}

def is_v0_safe_candidate(row, wallet):
    if row["wallet_age_days"] < 7:
        return False
    if row["tx_per_day"] > 50:
        return False
    if row["avg_tx"] < 0.001:
        return False
    if row["avg_tx"] < 0.01 and row["tx_per_day"] > 20:
        return False

    if wallet in _keyword_cache:
        keyword_label = _keyword_cache[wallet]
    else:
        keyword_label = check_wallet_keywords(wallet)
        _keyword_cache[wallet] = keyword_label

    if keyword_label == 1:
        return False

    return True


def is_v4_high_confidence_candidate(row, wallet):
    if row["wallet_age_days"] < 30:
        return False
    if row["tx_per_day"] > 20:
        return False
    if row["tx_per_hour"] > 8:
        return False
    if row["avg_tx"] < 0.01:
        return False
    if row["avg_time_between_tx_sec"] < 1800:
        return False
    if row["avg_tx"] < 0.05 and row["tx_per_day"] > 10:
        return False

    if wallet in _keyword_cache:
        keyword_label = _keyword_cache[wallet]
    else:
        keyword_label = check_wallet_keywords(wallet)
        _keyword_cache[wallet] = keyword_label

    if keyword_label == 1:
        return False

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
                if is_v0_safe_candidate(row, w):
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

            row = {"wallet": w, "token": token.lower(), **base}

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