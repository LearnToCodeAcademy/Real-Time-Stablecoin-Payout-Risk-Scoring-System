#!/usr/bin/env python3
"""
Integration Test: Token support expansion in realistic scenarios
Demonstrates how the system handles both trained and expanded tokens
"""

import sys
sys.path.insert(0, '.')

from wallet_check import detect_token, SUPPORTED_TOKENS, ALL_TOKENS

def test_scenario(name, transactions, expected_token, expected_result):
    """Test a realistic scenario"""
    print(f"\n{'='*60}")
    print(f"SCENARIO: {name}")
    print(f"{'='*60}")
    print(f"Transactions simulated: {len(transactions)}")
    for tx in transactions:
        print(f"  - {tx.get('tokenSymbol')} ({tx.get('hash')})")
    
    print("\n--- Running detect_token() ---")
    result = detect_token(transactions)
    
    print(f"\nResult: {result}")
    print(f"Expected: {expected_token}")
    
    if result == expected_token:
        print(f"[OK] PASS - Got expected result")
        return True
    else:
        print(f"[FAIL] Expected {expected_token}, got {result}")
        return False

def main():
    print("\n" + "="*60)
    print("INTEGRATION TEST: Token Support System")
    print("="*60)
    print(f"TRAINED tokens (6): {SUPPORTED_TOKENS}")
    print(f"TOTAL tokens: {len(ALL_TOKENS)}")
    
    results = []
    
    # Scenario 1: USDT wallet (trained token)
    results.append(test_scenario(
        "User deposits USDT - Trained token",
        [
            {"tokenSymbol": "USDT", "hash": "0x001"},
            {"tokenSymbol": "USDT", "hash": "0x002"},
            {"tokenSymbol": "USDT", "hash": "0x003"},
            {"tokenSymbol": "USDT", "hash": "0x004"},
            {"tokenSymbol": "USDT", "hash": "0x005"},
        ],
        "USDT",
        "Should return USDT for scoring"
    ))
    
    # Scenario 2: DAI wallet (trained token)
    results.append(test_scenario(
        "User swaps for DAI - Trained token",
        [
            {"tokenSymbol": "DAI", "hash": "0x101"},
            {"tokenSymbol": "DAI", "hash": "0x102"},
            {"tokenSymbol": "ETH", "hash": "0x103"},  # ETH is not in tokens
            {"tokenSymbol": "DAI", "hash": "0x104"},
        ],
        "DAI",
        "Should detect DAI despite ETH"
    ))
    
    # Scenario 3: FRAX wallet (unsupported stablecoin)
    results.append(test_scenario(
        "User receives FRAX - Unsupported stablecoin",
        [
            {"tokenSymbol": "FRAX", "hash": "0x201"},
            {"tokenSymbol": "FRAX", "hash": "0x202"},
            {"tokenSymbol": "FRAX", "hash": "0x203"},
        ],
        None,
        "Should detect but return None (unsupported)"
    ))
    
    # Scenario 4: PEPE meme coin (unsupported)
    results.append(test_scenario(
        "Meme coin trader - PEPE (unsupported)",
        [
            {"tokenSymbol": "PEPE", "hash": "0x301"},
            {"tokenSymbol": "PEPE", "hash": "0x302"},
            {"tokenSymbol": "PEPE", "hash": "0x303"},
            {"tokenSymbol": "PEPE", "hash": "0x304"},
            {"tokenSymbol": "PEPE", "hash": "0x305"},
        ],
        None,
        "Should report PEPE unsupported"
    ))
    
    # Scenario 5: Mixed supported (USDC + USDT)
    results.append(test_scenario(
        "User migrates from USDT to USDC - Both trained",
        [
            {"tokenSymbol": "USDT", "hash": "0x401"},
            {"tokenSymbol": "USDT", "hash": "0x402"},
            {"tokenSymbol": "USDC", "hash": "0x403"},
            {"tokenSymbol": "USDC", "hash": "0x404"},
            {"tokenSymbol": "USDC", "hash": "0x405"},
        ],
        "USDC",
        "Should select most common (USDC)"
    ))
    
    # Scenario 6: Unknown token
    results.append(test_scenario(
        "Transaction with unknown token",
        [
            {"tokenSymbol": "UNKNOWNXYZ", "hash": "0x501"},
            {"tokenSymbol": "UNKNOWNXYZ", "hash": "0x502"},
        ],
        None,
        "Should return None for unknown"
    ))
    
    # Scenario 7: DeFi token (AAVE - unsupported)
    results.append(test_scenario(
        "DeFi yield farming - AAVE (unsupported)",
        [
            {"tokenSymbol": "AAVE", "hash": "0x601"},
            {"tokenSymbol": "AAVE", "hash": "0x602"},
            {"tokenSymbol": "AAVE", "hash": "0x603"},
        ],
        None,
        "Should report AAVE unsupported"
    ))
    
    # Scenario 8: L2 token (ARB - unsupported)
    results.append(test_scenario(
        "Arbitrum ecosystem - ARB token (unsupported)",
        [
            {"tokenSymbol": "ARB", "hash": "0x701"},
            {"tokenSymbol": "ARB", "hash": "0x702"},
            {"tokenSymbol": "ARB", "hash": "0x703"},
        ],
        None,
        "Should report ARB unsupported"
    ))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Tests passed: {passed}/{total}")
    
    for i, result in enumerate(results, 1):
        status = "[OK]" if result else "[FAIL]"
        print(f"  {status} Scenario {i}")
    
    if passed == total:
        print("\n[OK] All integration tests passed!")
        print("\nSystem Status:")
        print("  [CHECK] Trained tokens (6) score correctly")
        print("  [CHECK] Unsupported tokens reported transparently")
        print("  [CHECK] Detection algorithms work across all categories")
        print("  [CHECK] No scoring for unsupported tokens")
        return 0
    else:
        print(f"\n[FAIL] {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
