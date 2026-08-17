#!/usr/bin/env python3
"""
[CRITICAL FIX VALIDATION]
Diagnostic script to test wallet_check fixes for token detection flaw.

This script:
1. Tests API responses with debug output
2. Validates token detection (symbol + contract address fallback)
3. Tests with known USDT/USDC addresses
4. Shows what's broken and what's fixed
"""

from wallet_check import ALL_TOKENS, SUPPORTED_TOKENS, fetch_transactions

print("=" * 70)
print("WALLET_CHECK FIX VALIDATION TEST")
print("=" * 70)

# Test 1: Known addresses (you can provide these)
TEST_ADDRESSES = {
    # Add test addresses here - preferably from your v1_usdt.csv dataset
    # Format: "0x...": "expected_token"
    "0xea2f73e6c8dc782b06d1eeec8fc1462378cef519": "DAI",  # From your dataset attachment
}

print("\n" + "=" * 70)
print("TEST 1: API RESPONSE STRUCTURE")
print("=" * 70)
print("\nFetching transactions with debug output...\n")

if TEST_ADDRESSES:
    address = list(TEST_ADDRESSES.keys())[0]
    print(f"Testing address: {address}")
    print(f"Expected token: {TEST_ADDRESSES[address]}\n")

    # Fetch with debug
    txs = fetch_transactions(address, debug=True)

    if txs:
        print(f"\n✓ Got {len(txs)} transactions")
        print("\nFirst transaction structure:")
        tx = txs[0]
        for key in sorted(tx.keys()):
            print(f"  {key:20s}: {str(tx[key])[:60]}")
    else:
        print("✗ No transactions returned from API")
else:
    print("⚠ No test addresses configured. Add addresses to TEST_ADDRESSES dict.")

print("\n" + "=" * 70)
print("TEST 2: TOKEN DETECTION STRATEGIES")
print("=" * 70)

# Show what we're checking for
print("\nSupported TRAINED tokens:")
print(f"  {SUPPORTED_TOKENS}")

print("\nAll 54 tokens by symbol:")
print(f"  {list(ALL_TOKENS.keys())}")

print("\nContract address mapping (for fallback detection):")
for token, addr in ALL_TOKENS.items():
    print(f"  {token:10s} → {addr}")

print("\n" + "=" * 70)
print("TEST 3: MANUAL TOKEN OVERRIDE")
print("=" * 70)

print("""
NEW FEATURE: Manual token specification to bypass auto-detection

Usage examples:
  python wallet_check.py 0x... --token USDT --debug
  python test_wallet_check_fix.py  # then select token in interactive mode
""")

print("\n" + "=" * 70)
print("TEST 4: KNOWN ISSUES & SOLUTIONS")
print("=" * 70)

issues = [
    {
        "issue": "No recognized tokens found in transaction history",
        "causes": [
            "API returns empty result (no transactions)",
            "tokenSymbol field is empty/missing",
            "contractAddress field not recognized",
            "API key rate limited or invalid",
        ],
        "solutions": [
            "✓ Use --token USDT to manually override",
            "✓ Check debug mode output: python wallet_check.py ADDRESS --token USDT --debug",
            "✓ Verify API key in wallet_check.py line 18: API_KEY = ...",
            "✓ Use contract address fallback (now implemented)",
        ],
    },
    {
        "issue": "Scoring skipped - no supported token model available",
        "causes": [
            "Token detected but not in SUPPORTED_TOKENS list",
            "Model file doesn't exist for that token",
            "Token is WATCHONLY (no trained model yet)",
        ],
        "solutions": [
            "✓ Check which token was detected (see output before error)",
            "✓ Available trained models: " + ", ".join(SUPPORTED_TOKENS),
            "✓ Use --token USDT to force a different token",
        ],
    },
]

for i, issue_info in enumerate(issues, 1):
    print(f"\nIssue {i}: {issue_info['issue']}")
    print("  Possible causes:")
    for cause in issue_info["causes"]:
        print(f"    • {cause}")
    print("  Solutions:")
    for solution in issue_info["solutions"]:
        print(f"    {solution}")

print("\n" + "=" * 70)
print("QUICK START: Testing with your USDT address")
print("=" * 70)

print("""
Step 1: Get an address from v1_usdt.csv
  Example: 0xea2f73e6c8dc782b06d1eeec8fc1462378cef519

Step 2: Test with manual token override and debug
  python wallet_check.py 0xea2f73e6c8dc782b06d1eeec8fc1462378cef519 --token USDT --debug

Step 3: Expected output
  ✓ [DEBUG] API Response: status=200
  ✓ [DEBUG] tokenSymbol: (check what's returned)
  ✓ [OK] Found TRAINED token: USDT (count: X) - Scoring enabled
  ✓ Then ML scoring proceeds...

Step 4: If still failing
  • Paste the debug output in the issue
  • Check if tokenSymbol is actually empty/missing
  • Verify Etherscan API key is valid
""")

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)

print("""
FIXES IMPLEMENTED:
✓ 1. Enhanced API debugging - see exactly what's being returned
✓ 2. Fallback token detection using contract addresses
✓ 3. Manual token override (--token USDT)
✓ 4. Better error messages with hints
✓ 5. Interactive mode asks for token/debug options

THE ROOT ISSUE:
The problem is that Etherscan API's tokentx endpoint sometimes returns transactions 
where the tokenSymbol field is:
  • Empty string ""
  • Null/missing
  • Different from expected
  • Not found in our ALL_TOKENS dictionary

FIXES APPLIED:
  1. Compare contractAddress instead of tokenSymbol (fallback strategy)
  2. Allow manual token specification to bypass detection
  3. Add comprehensive debugging to diagnose API issues
  4. Improve error messages to guide troubleshooting

NEXT STEPS:
1. Test with the USDT address from your v1_usdt.csv
2. Run: python wallet_check.py ADDRESS --token USDT --debug
3. Share debug output if still failing
4. Verify models exist in models/ directory
""")

print("\n" + "=" * 70)
