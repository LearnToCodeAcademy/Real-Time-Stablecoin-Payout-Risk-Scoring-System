import pandas as pd
import pickle
import numpy as np

# =============================
# LOAD MODEL
# =============================
with open("models/usdt_model.pkl", "rb") as f:
    model = pickle.load(f)

with open("models/usdt_scaler.pkl", "rb") as f:
    scaler = pickle.load(f)

with open("models/usdt_features.pkl", "rb") as f:
    feature_cols = pickle.load(f)

# =============================
# SAMPLE INPUT (replace later)
# =============================
sample = pd.DataFrame([{
    "wallet_age_days": 5,
    "avg_tx": np.log1p(10),
    "recent_tx": np.log1p(12),
    "tx_frequency": 2,
    "tx_per_min": 0.1,
    "tx_per_hour": 6,
    "tx_per_day": 50,
    "avg_time_between_tx_sec": 120
}])

# =============================
# SCALE
# =============================
sample_scaled = scaler.transform(sample[feature_cols])

# =============================
# PREDICT
# =============================
prob = model.predict_proba(sample_scaled)[0][1]

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

decision = classify_risk(prob)

# =============================
# OUTPUT
# =============================
confidence = abs(prob - 0.5) * 2

print("\n? FINAL OUTPUT")
print(f"Risk Probability: {prob:.4f}")
print(f"Decision: {decision}")
print(f"Confidence: {confidence:.4f}")