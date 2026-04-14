import pandas as pd

INPUT_PATH = "datasets/usdt_training_ready.csv"
OUTPUT_PATH = "datasets/usdt_labeled_v4.csv"
MAX_V4 = 2000

print("🚀 Loading dataset...")

df = pd.read_csv(INPUT_PATH)
print(f"📊 Loaded rows: {len(df)}")

# REMOVE LEAKAGE
df = df.drop(columns=[
    "risk_probability",
    "prediction",
    "decision",
    "confidence"
], errors="ignore")

# STRICT SAFE FILTER
safe_df = df[
    (df["is_high_freq"] == False) &
    (df["is_low_value"] == False) &
    (df["is_new_wallet"] == False) &
    (df["tx_per_day"] < 20) &
    (df["wallet_age_days"] > 120) &
    (df["avg_tx"] > 1) &
    (df["risk_score_rule"] == 0)
].copy()

print(f"✅ After filtering: {len(safe_df)} wallets")

# 🔥 OPTIONAL FIX (recommended)
safe_df = safe_df.drop_duplicates(subset=["wallet"])

# ADD V3 FEATURES
safe_df["dust_tx_ratio"] = 0
safe_df["similarity_hits"] = 0
safe_df["new_sender_ratio"] = 0
safe_df["is_poisoned_pattern"] = 0

# LABEL
safe_df["label"] = 0

# BALANCE SIZE
if len(safe_df) > MAX_V4:
    safe_df = safe_df.sample(MAX_V4, random_state=42)
    print(f"⚠️ Trimmed to {MAX_V4}")

FINAL_COLS = [
    "wallet","token","wallet_age_days","avg_tx","recent_tx",
    "tx_frequency","tx_per_min","tx_per_hour","tx_per_day",
    "avg_time_between_tx_sec","is_high_freq","is_low_value",
    "is_new_wallet","risk_score_rule","dust_tx_ratio",
    "similarity_hits","new_sender_ratio","is_poisoned_pattern","label"
]

FINAL_COLS = [c for c in FINAL_COLS if c in safe_df.columns]
safe_df = safe_df[FINAL_COLS]

safe_df.to_csv(OUTPUT_PATH, index=False)

print(f"\n🔥 V4 SAVED → {OUTPUT_PATH}")
print(f"📊 Final rows: {len(safe_df)}")