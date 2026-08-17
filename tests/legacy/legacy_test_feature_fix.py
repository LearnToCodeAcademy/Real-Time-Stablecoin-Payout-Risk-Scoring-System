"""
Quick test to verify feature extraction includes all 19 features.
"""

import pickle

from wallet_check import generate_features

# Load expected features from a trained model
features_expected = pickle.load(open("models/tusd_features.pkl", "rb"))
print(f"Expected features ({len(features_expected)}): {features_expected}\n")

# Create fake transaction data to test
fake_txs = [
    {
        "value": "1000000000000000000",
        "tokenDecimal": "18",
        "from": "0x8fc101291c3047965b3f82cd0624a7a6436257c8",
        "timeStamp": "1700000000",
    },
    {
        "value": "100000000000000000",
        "tokenDecimal": "18",
        "from": "0x8fc101291c3047965b3f82cd0624a7a6436257c8",
        "timeStamp": "1700001000",
    },
    {
        "value": "50000000000000000",
        "tokenDecimal": "18",
        "from": "0x8fc101291c3047965b3f82cd0624a7a6436357c8",
        "timeStamp": "1700002000",
    },
    {
        "value": "10000000000000000",
        "tokenDecimal": "18",
        "from": "0x8fc101291c3047965b3f82cd0624a7a6436357c8",
        "timeStamp": "1700003000",
    },  # Dust
    {
        "value": "1000000000000000",
        "tokenDecimal": "18",
        "from": "0x8fc101291c3047965b3f82cd0624a7a6436357c8",
        "timeStamp": "1700004000",
    },  # Dust
]

# Test feature extraction with wallet address
features, low_data = generate_features(fake_txs, "0x8fc101291c3047965b3f82cd0624a7a6436257c8")

print(f"Generated features ({len(features)}): {list(features.keys())}\n")

# Check if all expected features are present
missing = set(features_expected) - set(features.keys())
print(f"Missing features: {missing if missing else 'NONE [OK]'}")

# Show specific V3 poisoning features
print("\nV3 Poisoning Features:")
print(f"  dust_tx_ratio: {features.get('dust_tx_ratio', 'MISSING')}")
print(f"  similarity_hits: {features.get('similarity_hits', 'MISSING')}")
print(f"  new_sender_ratio: {features.get('new_sender_ratio', 'MISSING')}")
print(f"  is_poisoned_pattern: {features.get('is_poisoned_pattern', 'MISSING')}")

if features.get("is_poisoned_pattern", 0) > 0:
    print("\n[OK] V3 Poisoning Detection is WORKING!")
else:
    print("\n[WARN] V3 Poisoning pattern not detected with test data (this may be expected)")
