
import pandas as pd
import numpy as np
import pickle

# =============================
# CONFIG 🔥 (CHANGE TOKEN HERE)
# =============================
TOKEN = "usdc"  # change to "usdt"

SYNTHETIC_PATH = f"datasets/{TOKEN}_training_ready.csv"

LABELED_V1_PATH = f"datasets/{TOKEN}_labeled_auto.csv"
LABELED_V2_PATH = f"datasets/{TOKEN}_labeled_v2.csv"  # 🔥 optional

MODEL_PATH = f"models/{TOKEN}_model.pkl"
SCALER_PATH = f"models/{TOKEN}_scaler.pkl"
FEATURE_PATH = f"models/{TOKEN}_features.pkl"

# =============================
# LOAD SYNTHETIC
# =============================
df_synth = pd.read_csv(SYNTHETIC_PATH)
print(f"📊 Synthetic rows: {len(df_synth)}")

# =============================
# LOAD LABELED V1 (HIGH QUALITY)
# =============================
df_v1 = pd.read_csv(LABELED_V1_PATH)
df_v1 = df_v1.dropna(subset=["label"])
df_v1["label"] = df_v1["label"].astype(int)

print(f"📊 Labeled V1 rows: {len(df_v1)}")

# =============================
# LOAD LABELED V2 (AUTO LARGE)
# =============================
USE_V2 = False  # 🔥 TOGGLE HERE

df_v2 = pd.DataFrame()

if USE_V2:
    try:
        df_v2 = pd.read_csv(LABELED_V2_PATH)
        df_v2 = df_v2.dropna(subset=["label"])
        df_v2["label"] = df_v2["label"].astype(int)

        print(f"📊 Labeled V2 rows: {len(df_v2)}")
    except Exception as e:
        print(f"⚠️ Failed loading V2: {e}")

# =============================
# COMBINE DATASETS 🔥
# =============================
df = pd.concat([df_synth, df_v1, df_v2], ignore_index=True)

print(f"📊 Total training rows: {len(df)}")

# =============================
# FEATURES
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
# WEIGHTS 🔥
# =============================
weights = np.concatenate([
    np.ones(len(df_synth)),          # synthetic → 1x
    np.ones(len(df_v1)) * 5,         # V1 → strong truth 🔥
    np.ones(len(df_v2)) * 2 if USE_V2 else np.array([])  # V2 → weaker
])

print("⚖️ Weights:")
print(f" - Synthetic: {len(df_synth)} rows (1x)")
print(f" - V1 labels: {len(df_v1)} rows (5x)")
if USE_V2:
    print(f" - V2 labels: {len(df_v2)} rows (2x)")

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

model = RandomForestClassifier(
    n_estimators=100,
    random_state=42
)

model.fit(X_scaled, y, sample_weight=weights)

# =============================
# SAVE MODEL 🔥
# =============================
with open(MODEL_PATH, "wb") as f:
    pickle.dump(model, f)

with open(SCALER_PATH, "wb") as f:
    pickle.dump(scaler, f)

with open(FEATURE_PATH, "wb") as f:
    pickle.dump(feature_cols, f)

print(f"\n🔥 {TOKEN.upper()} MODEL TRAINED & SAVED")

# =============================
# QUICK TEST
# =============================
sample = X.iloc[0:1]
sample_scaled = scaler.transform(sample)

prob = model.predict_proba(sample_scaled)[0][1]

print(f"\n🔥 Sample Risk Probability: {prob:.4f}")