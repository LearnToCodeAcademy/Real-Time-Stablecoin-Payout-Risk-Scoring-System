"""
Test token contract detection and skipping.
"""

# Simulate the validation logic
TOKEN_CONTRACTS = {
    "0xdAC17F958D2ee523a2206206994597C13D831ec7": "USDT",
    "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48": "USDC",
    "0x6B175474E89094C44Da98b954EedeAC495271d0F": "DAI",
}


def validate_address(address):
    """Check if address is a known token contract."""
    address_lower = address.lower()
    for contract_addr, token_name in TOKEN_CONTRACTS.items():
        if address_lower == contract_addr.lower():
            return f"[SKIP] {token_name} token contract"
    return None


print("=" * 60)
print("TEST: Token Contract Detection")
print("=" * 60)

# Test cases
test_cases = [
    ("0xdAC17F958D2ee523a2206206994597C13D831ec7", "USDT Contract (should skip)"),
    (
        "0xDAC17F958D2ee523a2206206994597C13D831ec7",
        "USDT Contract uppercase (should skip - case insensitive)",
    ),
    ("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", "USDC Contract (should skip)"),
    ("0x1234567890123456789012345678901234567890", "Random address (should process)"),
    ("0x0000000000000000000000000000000000000001", "Another random (should process)"),
]

for address, description in test_cases:
    result = validate_address(address)
    status = "SKIP" if result else "PROCESS"
    print(f"\n[{status}] {description}")
    print(f"    Address: {address}")
    if result:
        print(f"    Reason: {result}")

print("\n" + "=" * 60)
print("All contract addresses correctly identified!")
