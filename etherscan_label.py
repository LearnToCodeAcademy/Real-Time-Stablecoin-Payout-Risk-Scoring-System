import requests
import time
import re
from db import get_label, save_label

# =============================
# CONFIG
# =============================
# 🔥 UPGRADED HEADERS: Makes the request look like a real Chrome browser 
# to help bypass basic Cloudflare bot protection.
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://etherscan.io/",
    "Connection": "keep-alive"
}

TRUSTED_KEYWORDS = [
    "binance",
    "coinbase",
    "kraken",
    "okx",
    "bybit",
    "huobi",
    "kucoin",
    "gate.io",
    "exchange"
]

# =============================
# FETCH HTML
# =============================
def fetch_etherscan_page(address):
    try:
        url = f"https://etherscan.io/address/{address}"
        res = requests.get(url, headers=HEADERS, timeout=10)
        
        if res.status_code != 200:
            print(f"❌ Fetch error: HTTP {res.status_code}")
            return None
            
        return res.text
    except Exception as e:
        print("❌ Fetch error:", e)
        return None

# =============================
# EXTRACT LABEL (FIXED 🔥)
# =============================
def extract_label(html):
    if not html:
        return None

    # Check if Cloudflare blocked the request
    if "just a moment" in html.lower() or "cloudflare" in html.lower() or "challenge-platform" in html:
        print("⚠️ WARNING: Request was blocked by Cloudflare. HTML did not load.")
        return None

    # 🔥 METHOD 1: Target "Public Name Tag" tooltip (Most common for trusted exchanges)
    match = re.search(r'title="Public Name Tag:\s*([^"]+)"', html, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # 🔥 METHOD 2: Target account label links (e.g., <a href="/accounts/label/binance">Binance 16</a>)
    match = re.search(r'href="/accounts/label/[^"]+"[^>]*>(.*?)</a>', html, re.IGNORECASE)
    if match:
        # Strip out any nested HTML tags (like icons) inside the label text
        raw_label = match.group(1)
        clean_label = re.sub(r'<[^>]+>', '', raw_label).strip()
        if clean_label:
            return clean_label

    # 🔥 METHOD 3: Fallback to the old JSON variable method just in case
    match = re.search(r'"nameTag"\s*:\s*"([^"]+)"', html)
    if match:
        return match.group(1).strip()

    return None

# =============================
# TRUST CHECK
# =============================
def is_trusted(label):
    if not label:
        return False

    label = label.lower()

    for keyword in TRUSTED_KEYWORDS:
        if keyword in label:
            return True

    return False

# =============================
# MAIN FUNCTION
# =============================
def get_wallet_label(address):
    address = address.lower()

    # =============================
    # 1. CHECK DB FIRST
    # =============================
    try:
        cached = get_label(address)
        if cached:
            print("⚡ LABEL CACHE HIT:", cached)
            return cached
    except Exception as e:
        print("⚠️ DB read error:", e)

    # =============================
    # 2. SCRAPE
    # =============================
    html = fetch_etherscan_page(address)

    label = extract_label(html)

    print("🔍 Extracted label:", label)  # 🔥 DEBUG LINE

    trusted = is_trusted(label)

    result = {
        "label": label,
        "trusted": trusted
    }

    # =============================
    # 3. SAVE TO DB
    # =============================
    if label:
        try:
            save_label(address, label, trusted)
        except Exception as e:
            print("⚠️ DB write error:", e)

    # prevent rate limit
    time.sleep(1.0) # Increased slightly to 1s to further avoid Cloudflare triggers

    return result

# =============================
# TEST
# =============================
if __name__ == "__main__":
    wallet = input("Wallet: ")
    info = get_wallet_label(wallet)

    print("\nResult:")
    print(info)