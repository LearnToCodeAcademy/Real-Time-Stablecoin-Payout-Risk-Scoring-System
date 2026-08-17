#!/usr/bin/env python3
"""
Test: Verify expanded token support (48+ tokens) works correctly.
- TRAINED tokens (6): Should return token for scoring
- WATCHONLY tokens (42+): Should report unsupported and skip
"""

import sys

sys.path.insert(0, ".")

from wallet_check import ALL_TOKENS, SUPPORTED_TOKENS, detect_token


def test_trained_token_detection():
    """Test detecting a TRAINED token"""
    print("\n" + "=" * 60)
    print("TEST 1: TRAINED TOKEN DETECTION")
    print("=" * 60)

    # Mock USDT transaction
    usdt_txs = [
        {"tokenSymbol": "USDT", "hash": "0xabc"},
        {"tokenSymbol": "USDT", "hash": "0xdef"},
        {"tokenSymbol": "USDT", "hash": "0xghi"},
    ]

    result = detect_token(usdt_txs)

    if result == "USDT":
        print("[OK] TRAINED token USDT correctly returned for scoring")
        return True
    else:
        print(f"[FAIL] Expected USDT, got {result}")
        return False


def test_unsupported_token_detection():
    """Test detecting an UNSUPPORTED (watch-only) token"""
    print("\n" + "=" * 60)
    print("TEST 2: UNSUPPORTED TOKEN DETECTION")
    print("=" * 60)

    # Mock PEPE transaction (meme coin, not trained)
    pepe_txs = [
        {"tokenSymbol": "PEPE", "hash": "0xabc"},
        {"tokenSymbol": "PEPE", "hash": "0xdef"},
        {"tokenSymbol": "AAVE", "hash": "0xghi"},  # Different token
    ]

    result = detect_token(pepe_txs)

    if result is None:
        print("[OK] UNSUPPORTED token PEPE correctly returned None (no scoring)")
        return True
    else:
        print(f"[FAIL] Expected None for unsupported token, got {result}")
        return False


def test_token_list_expansion():
    """Verify ALL_TOKENS contains 48+ tokens"""
    print("\n" + "=" * 60)
    print("TEST 3: TOKEN LIST EXPANSION")
    print("=" * 60)

    print(f"TRAINED tokens (have models): {len(SUPPORTED_TOKENS)}")
    for t in SUPPORTED_TOKENS:
        print(f"  * {t}")

    print(f"\nTOTAL tokens in ALL_TOKENS: {len(ALL_TOKENS)}")

    # Count by category
    stables = [
        "USDT",
        "USDC",
        "DAI",
        "BUSD",
        "USDP",
        "TUSD",
        "FRAX",
        "USDX",
        "GUSD",
        "LUSD",
        "MIM",
        "USDD",
        "EURS",
        "DOLA",
    ]
    defi = ["AAVE", "COMP", "SNX", "UNI", "LINK", "SUSHI", "CRV", "1INCH"]
    eth_l2 = ["WETH", "MATIC", "LDO", "ARB", "OP", "GMX", "SOL"]
    wrapped = ["WBTC", "cBTC", "stETH", "rswETH", "CBETH", "LST"]
    meme = ["DOGE", "SHIB", "PEPE", "FLOKI", "BONK", "WLD"]

    print(f"\nStablecoins: {len(stables)} tokens")
    print(f"DeFi: {len(defi)} tokens")
    print(f"ETH/L2: {len(eth_l2)} tokens")
    print(f"Wrapped: {len(wrapped)} tokens")
    print(f"Meme/Other: {len(meme)} tokens")

    if len(ALL_TOKENS) >= 48:
        print(f"\n[OK] Token list expanded to {len(ALL_TOKENS)} tokens (target: 48+)")
        return True
    else:
        print(f"[FAIL] Token list has {len(ALL_TOKENS)} tokens, expected >= 48")
        return False


def test_all_trained_in_all_tokens():
    """Verify all TRAINED tokens are in ALL_TOKENS"""
    print("\n" + "=" * 60)
    print("TEST 4: TRAINED TOKENS IN ALL_TOKENS")
    print("=" * 60)

    missing = []
    for token in SUPPORTED_TOKENS:
        if token not in ALL_TOKENS:
            missing.append(token)

    if not missing:
        print(f"[OK] All {len(SUPPORTED_TOKENS)} trained tokens found in ALL_TOKENS")
        return True
    else:
        print(f"[FAIL] Missing trained tokens in ALL_TOKENS: {missing}")
        return False


def test_contract_addresses_present():
    """Verify all tokens have contract addresses"""
    print("\n" + "=" * 60)
    print("TEST 5: CONTRACT ADDRESSES")
    print("=" * 60)

    missing_addresses = []
    for token, address in ALL_TOKENS.items():
        if not isinstance(address, str) or not address.startswith("0x"):
            missing_addresses.append(token)

    if not missing_addresses:
        print(f"[OK] All {len(ALL_TOKENS)} tokens have valid contract addresses")
        return True
    else:
        print(f"[FAIL] Missing/invalid addresses: {missing_addresses}")
        return False


if __name__ == "__main__":
    print("\nTesting Expanded Token Support System")
    print("Current SUPPORTED_TOKENS (trained):", SUPPORTED_TOKENS)
    print("Total tokens in system:", len(ALL_TOKENS))

    results = []
    results.append(test_trained_token_detection())
    results.append(test_unsupported_token_detection())
    results.append(test_token_list_expansion())
    results.append(test_all_trained_in_all_tokens())
    results.append(test_contract_addresses_present())

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Tests passed: {passed}/{total}")

    if passed == total:
        print("[OK] All token expansion tests passed!")
    else:
        print(f"[FAIL] {total - passed} tests failed")
        sys.exit(1)
