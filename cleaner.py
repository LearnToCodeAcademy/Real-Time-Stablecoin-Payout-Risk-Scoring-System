import pandas as pd
import numpy as np

# =============================
# CONFIG
# =============================
THRESHOLD = 0.4
np.random.seed(42)

# =============================
# LOAD DATA
# =============================
df = pd.read_csv("datasets/usdt_datasets.csv")

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

df["wallet_age_days"] = df["wallet_age_days"].apply(lambda x: max(x, 1))

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

df["avg_tx"] = df["avg_tx"].round(6)
df["recent_tx"] = df["recent_tx"].round(6)

df["avg_tx"] = np.log1p(df["avg_tx"])
df["recent_tx"] = np.log1p(df["recent_tx"])

df["wallet"] = df["wallet"].astype(str)
df["token"] = df["token"].astype(str)

# =============================
# RULE FEATURES
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
# REALISTIC LABEL
# =============================
df["label"] = (
    (df["tx_per_day"] > 150) |
    (df["avg_tx"] < np.log1p(0.005)) |
    (df["wallet_age_days"] < 2)
).astype(int)

noise = np.random.rand(len(df)) < 0.05
df.loc[noise, "label"] = 1 - df.loc[noise, "label"]

# =============================
# FEATURES (FOR ML)
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

X = df[feature_cols]
y = df["label"]

# =============================
# NORMALIZE
# =============================
from sklearn.preprocessing import StandardScaler

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# =============================
# TRAIN MODEL
# =============================
from sklearn.ensemble import RandomForestClassifier

model = RandomForestClassifier(n_estimators=100)
model.fit(X_scaled, y)

# =============================
# PREDICTIONS (FULL DATASET)
# =============================
df["risk_probability"] = model.predict_proba(X_scaled)[:, 1]

df["prediction"] = (df["risk_probability"] > THRESHOLD).astype(int)

# =============================
# DECISION ENGINE
# =============================
def classify_risk(prob):
    if prob >= 0.8:
        return "BLOCK"
    elif prob >= 0.5:
        return "REVIEW"
    else:
        return "ALLOW"

df["decision"] = df["risk_probability"].apply(classify_risk)

# =============================
# CONFIDENCE SCORE
# =============================
df["confidence"] = np.abs(df["risk_probability"] - 0.5) * 2

# =============================
# GLOBAL STATS
# =============================
print("\n🔥 Global Risk Stats:")
print(f"Avg Risk: {df['risk_probability'].mean():.4f}")
print(f"Max Risk: {df['risk_probability'].max():.4f}")
print(f"Min Risk: {df['risk_probability'].min():.4f}")

print("\n🔥 Decision Distribution:")
print(df["decision"].value_counts())

# =============================
# FEATURE IMPORTANCE
# =============================
feature_importance = pd.Series(model.feature_importances_, index=feature_cols)
feature_importance = feature_importance.sort_values(ascending=False)

print("\n🔥 Feature Importance:")
print(feature_importance)

# =============================
# FINAL SAVE (🔥 IMPORTANT)
# =============================
df.to_csv("datasets/usdt_training_ready.csv", index=False)

print("\n✅ FINAL TRAINING DATASET READY")