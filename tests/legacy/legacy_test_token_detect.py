"""
Test improved token detection.
"""

# Simulate API response with token data
test_txs = [
    {"from": "0x1", "to": "0x2", "value": "100", "tokenDecimal": "6", "tokenSymbol": "USDT"},
    {"from": "0x1", "to": "0x2", "value": "50", "tokenDecimal": "6", "tokenSymbol": "USDT"},
    {"from": "0x1", "to": "0x2", "value": "30", "tokenDecimal": "18", "tokenSymbol": "DAI"},
    {"from": "0x1", "to": "0x2", "value": "20", "tokenDecimal": "6", "tokenSymbol": "USDC"},
    {
        "from": "0x1",
        "to": "0x2",
        "value": "10",
        "tokenDecimal": "6",
        "tokenSymbol": "UNKNOWN",
    },  # Unknown token
    {"from": "0x1", "to": "0x2", "value": "5", "tokenDecimal": "18", "tokenSymbol": "USDT"},
]


# Simulate old logic
def detect_token_old(transactions):
    counts = {}
    supported = ["USDT", "USDC", "DAI"]  # Simulated supported
    for tx in transactions:
        if isinstance(tx, dict):
            sym = tx.get("tokenSymbol")
            if isinstance(sym, str):
                sym = sym.upper().strip()
            if sym in supported:
                counts[sym] = counts.get(sym, 0) + 1
    return max(counts, key=counts.get) if counts else None


# Simulate new logic
def detect_token_new(transactions):
    """Detect token from top 20 transactions (as returned by API sorted by desc)."""
    counts = {}
    supported = ["USDT", "USDC", "DAI"]  # Simulated supported
    all_tokens = {}  # Track ALL tokens, not just supported

    # Extract from top 20 transactions (API returns sorted by desc)
    for tx in transactions[:20]:  # Top 20 most recent
        if isinstance(tx, dict):
            sym = tx.get("tokenSymbol")
            if isinstance(sym, str):
                sym = sym.upper().strip()
                all_tokens[sym] = all_tokens.get(sym, 0) + 1

                # Also count if supported
                if sym in supported:
                    counts[sym] = counts.get(sym, 0) + 1

    # Return supported token if found
    if counts:
        top_token = max(counts, key=counts.get)
        print(f"[OK] Found token: {top_token} (count: {counts[top_token]})")
        return top_token

    # If no supported token found, check what tokens exist
    if all_tokens:
        top_token = max(all_tokens, key=all_tokens.get)
        print(f"[WARN] Top token '{top_token}' not in trained models (supported: {supported})")
        print(f"[WARN] Available tokens in transactions: {list(all_tokens.keys())}")
        # Try to match by partial name or use the top one anyway
        for token in supported:
            if token in all_tokens:
                print(f"[OK] Using fallback: {token}")
                return token

    print("[WARN] No tokens detected in top 20 transactions")
    return None


print("=" * 60)
print("TEST: Token Detection Improvement")
print("=" * 60)
print("\nTransactions (USDT: 3, DAI: 1, USDC: 1, UNKNOWN: 1)\n")

print("OLD LOGIC:")
old_result = detect_token_old(test_txs)
print(f"Result: {old_result}\n")

print("NEW LOGIC:")
new_result = detect_token_new(test_txs)
print(f"Result: {new_result}\n")

if old_result == new_result:
    print("[OK] Both detect same supported token (USDT)")
else:
    print("[WARN] Different results - check implementation")
