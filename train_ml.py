import pandas as pd
import numpy as np
import pickle

# =============================
# LOAD TRAINING DATA
# =============================
df = pd.read_csv("datasets/usdt_training_ready.csv")

# =============================
# FEATURES (MUST MATCH TRAINING)
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
# SCALE FEATURES
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
# SAVE EVERYTHING 🔥
# =============================
with open("models/usdt_model.pkl", "wb") as f:
    pickle.dump(model, f)

with open("models/usdt_scaler.pkl", "wb") as f:
    pickle.dump(scaler, f)

with open("models/usdt_features.pkl", "wb") as f:
    pickle.dump(feature_cols, f)

print("🔥 USDT MODEL TRAINED & SAVED")

# =============================
# QUICK TEST (VERY IMPORTANT)
# =============================
sample = X.iloc[0:1]

sample_scaled = scaler.transform(sample)
prob = model.predict_proba(sample_scaled)[0][1]

print(f"\n🔥 Sample Risk Probability: {prob:.4f}")