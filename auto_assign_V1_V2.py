import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import os

# =============================
# 🔥 CONFIG (MULTI-TOKEN)
# =============================
TOKEN = "usdt"      # 🔥 Change to: usdt, usdc, busd, dai, usdp, tusd
VERSION = "v2"      # 🔥 Change to: v1 or v2

INPUT_CSV = f"datasets/{VERSION}_{TOKEN.lower()}.csv"
OUTPUT_CSV = f"datasets/{TOKEN.lower()}_labeled_{VERSION}.csv"  # v1→auto, v2→v2

SAVE_EVERY = 25        # autosave every N wallets
SLEEP = 1.2            # avoid rate limit

KEYWORDS = ["phish", "scam", "spam", "hack", "exploit", "malicious"]

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# =============================
# LOAD CSV
# =============================
df = pd.read_csv(INPUT_CSV)

# 🔥 ensure label column exists
if "label" not in df.columns:
    df["label"] = None

print(f"📊 Loaded {len(df)} rows")

# =============================
# RESUME SUPPORT 🔥
# =============================
start_index = 0

if os.path.exists(OUTPUT_CSV):
    print("🔁 Resuming from existing output file...")
    df_existing = pd.read_csv(OUTPUT_CSV)

    # merge labels from previous run
    if "label" in df_existing.columns:
        df["label"] = df_existing["label"]

    # find first unlabeled index
    unlabeled = df[df["label"].isna()]

    if not unlabeled.empty:
        start_index = unlabeled.index[0]
        print(f"▶️ Resuming from index {start_index}")
    else:
        print("✅ All rows already labeled")
        exit()

# =============================
# CHECK FUNCTION
# =============================
def check_wallet(address):
    url = f"https://etherscan.io/address/{address}"

    try:
        res = requests.get(url, headers=HEADERS, timeout=10)

        if res.status_code != 200:
            return None

        soup = BeautifulSoup(res.text, "html.parser")
        text = soup.get_text().lower()

        for kw in KEYWORDS:
            if kw in text:
                return 1  # 🚨 suspicious

        return None  # unknown

    except Exception as e:
        print(f"❌ Error: {e}")
        return None

# =============================
# PROCESS
# =============================
processed = 0

for i in range(start_index, len(df)):

    if not pd.isna(df.at[i, "label"]):
        continue

    wallet = df.at[i, "wallet"]

    print(f"🔍 [{i}/{len(df)}] Checking: {wallet}")

    result = check_wallet(wallet)

    if result == 1:
        df.at[i, "label"] = 1
        print("→ 🚨 SCAM detected")
    else:
        print("→ ⚠️ No signal (skipped)")

    processed += 1

    # 🔥 autosave
    if processed % SAVE_EVERY == 0:
        df.to_csv(OUTPUT_CSV, index=False)
        print(f"💾 Autosaved at {i}")

    time.sleep(SLEEP)

# =============================
# FINAL SAVE
# =============================
df.to_csv(OUTPUT_CSV, index=False)

print("\n🔥 AUTO-LABEL COMPLETE")
print(f"📁 Saved to: {OUTPUT_CSV}")

# =============================
# STATS
# =============================
labeled_count = df["label"].notna().sum()
scam_count = (df["label"] == 1).sum()

print(f"\n📊 SUMMARY:")
print(f"Total rows: {len(df)}")
print(f"Labeled (1): {scam_count}")
print(f"Unlabeled: {len(df) - labeled_count}")