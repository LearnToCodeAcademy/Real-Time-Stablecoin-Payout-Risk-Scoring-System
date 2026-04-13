
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time

# =============================
# CONFIG
# =============================
INPUT_CSV = "one_checker_output.csv"
OUTPUT_CSV = "datasets/usdt_labeled_auto.csv"

KEYWORDS = ["phish", "scam", "spam", "hack", "exploit", "malicious"]

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# =============================
# LOAD CSV
# =============================
df = pd.read_csv(INPUT_CSV)

# =============================
# CHECK FUNCTION
# =============================
def check_wallet(address):
    url = f"https://etherscan.io/address/{address}"

    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")

        text = soup.get_text().lower()

        for kw in KEYWORDS:
            if kw in text:
                return 1  # suspicious

        return None  # unknown → DO NOT force safe

    except Exception as e:
        print(f"❌ Error: {e}")
        return None

# =============================
# PROCESS CSV
# =============================
for i, row in df.iterrows():
    if pd.isna(row["label"]):  # ONLY EMPTY LABELS

        wallet = row["wallet"]
        print(f"🔍 Checking: {wallet}")

        result = check_wallet(wallet)

        if result == 1:
            df.at[i, "label"] = 1
            print("→ 🚨 Marked as SCAM (1)")

        else:
            print("→ ⚠️ No strong signal (skipped)")

        time.sleep(1.2)  # avoid rate limit

# =============================
# SAVE RESULT
# =============================
df.to_csv(OUTPUT_CSV, index=False)

print("\n✅ Auto-labeling complete → saved file")