import pandas as pd
from wallet_check import fetch_transactions, generate_features, save_feature, detect_token, backup_if_needed

INPUT_CSV = "batch_scan/wallets.csv"

df = pd.read_csv(INPUT_CSV)

for wallet in df["wallet"]:
    print(f"\nProcessing {wallet}")

    txs = fetch_transactions(wallet)

    if not txs:
        print("⚠️ No transactions")
        continue

    token = detect_token(txs)
    features = generate_features(txs)

    if not features:
        print("⚠️ Not enough data")
        continue

    changed = save_feature(wallet, token, features)

    if changed:
        backup_if_needed()

print("\n✅ Batch complete")