import pandas as pd
import numpy as np

# =============================
# CONFIG
# =============================
INPUT_PATH = "datasets/usdc_datasets.csv"
OUTPUT_PATH = "datasets/usdc_training_ready.csv"

np.random.seed(42)

# =============================
# LOAD DATA
# =============================
df = pd.read_csv(INPUT_PATH)

print(f"📥 Loaded dataset: {len(df)} rows")

# =============================
# CLEANING
# =============================
numeric_cols = [
    "tx_per_min",
    "tx_per_hour",
    "tx_per_day",
    "avg_time_between_tx_sec"
]

for col in numeric_cols:
    df[col] = df[col].fillna(0)

# Ensure wallet age is valid
df["wallet_age_days"] = df["wallet_age_days"].apply(lambda x: max(x, 1))

# =============================
# AGGREGATE PER WALLET
# =============================
df = df.groupby(["wallet", "token"], as_index=False).agg({
    "wallet_age_days": "max",
    "avg_tx": "mean",
    "recent_tx": "last",
    "tx_frequency": "mean",
    "tx_per_min": "mean",
    "tx_per_hour": "mean",
    "tx_per_day": "mean",
    "avg_time_between_tx_sec": "mean"
})

# =============================
# ROUND + TRANSFORM
# =============================
df["avg_tx"] = df["avg_tx"].round(6)
df["recent_tx"] = df["recent_tx"].round(6)

# log transform (important for ML stability)
df["avg_tx"] = np.log1p(df["avg_tx"])
df["recent_tx"] = np.log1p(df["recent_tx"])

df["wallet"] = df["wallet"].astype(str)
df["token"] = df["token"].astype(str)

# =============================
# RULE-BASED FEATURES
# =============================
df["is_high_freq"] = df["tx_per_day"] > 100
df["is_low_value"] = df["avg_tx"] < np.log1p(0.01)
df["is_new_wallet"] = df["wallet_age_days"] <= 3

df["risk_score_rule"] = (
    df["is_high_freq"].astype(int) * 0.5 +
    df["is_low_value"].astype(int) * 0.3 +
    df["is_new_wallet"].astype(int) * 0.2
)

# =============================
# LABEL GENERATION (SUPERVISED TARGET)
# =============================
df["label"] = (
    (df["tx_per_day"] > 150) |
    (df["avg_tx"] < np.log1p(0.005)) |
    (df["wallet_age_days"] < 2)
).astype(int)

# Add noise for realism (prevents overfitting)
noise = np.random.rand(len(df)) < 0.05
df.loc[noise, "label"] = 1 - df.loc[noise, "label"]

# =============================
# FINAL FEATURE SET
# =============================
feature_cols = [
    "wallet_age_days",
    "avg_tx",
    "recent_tx",
    "tx_frequency",
    "tx_per_min",
    "tx_per_hour",
    "tx_per_day",
    "avg_time_between_tx_sec"
]

print("\n🧠 Final Features:")
for f in feature_cols:
    print("-", f)

# =============================
# DATASET SUMMARY
# =============================
print("\n🔥 Dataset Summary:")
print(df["label"].value_counts())

print("\n📊 Basic Stats:")
print(df[feature_cols].describe().round(3))

# =============================
# SAVE CLEAN DATASET
# =============================
df.to_csv(OUTPUT_PATH, index=False)

print(f"\n✅ Saved cleaned dataset → {OUTPUT_PATH}")
print("🚀 Ready for training (train_ml.py)")