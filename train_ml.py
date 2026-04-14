import pandas as pd
import numpy as np
import pickle

# =============================
# CONFIG 🔥
# =============================
TOKEN = "usdt"

SYNTHETIC_PATH = f"datasets/{TOKEN}_training_ready.csv"
V1_PATH = f"datasets/{TOKEN}_labeled_auto.csv"
V2_PATH = f"datasets/{TOKEN}_labeled_v2.csv"
V3_PATH = f"datasets/{TOKEN}_labeled_v3.csv"
V4_PATH = f"datasets/{TOKEN}_labeled_v4.csv"

MODEL_PATH = f"models/{TOKEN}_model.pkl"
SCALER_PATH = f"models/{TOKEN}_scaler.pkl"
FEATURE_PATH = f"models/{TOKEN}_features.pkl"

USE_V2 = True
USE_V3 = True
USE_V4 = True

# =============================
# LOAD FUNCTION 🔥 (SAFE)
# =============================
def load_dataset(path, log_transform=True):
    try:
        df = pd.read_csv(path)

        if df.empty:
            return pd.DataFrame()

        df = df.dropna(subset=["label"])
        df["label"] = df["label"].astype(int)

        if "token" in df.columns:
            df["token"] = df["token"].astype(str).str.upper()

        # ✅ SAFE LOG TRANSFORM (prevents double log)
        if log_transform and df["avg_tx"].max() > 50:
            df["avg_tx"] = np.log1p(df["avg_tx"])
            df["recent_tx"] = np.log1p(df["recent_tx"])

        return df

    except Exception as e:
        print(f"⚠️ Failed loading {path}: {e}")
        return pd.DataFrame()

# =============================
# LOAD DATASETS
# =============================
df_synth = load_dataset(SYNTHETIC_PATH)
df_v1 = load_dataset(V1_PATH)
df_v2 = load_dataset(V2_PATH) if USE_V2 else pd.DataFrame()
df_v3 = load_dataset(V3_PATH, log_transform=False) if USE_V3 else pd.DataFrame()
df_v4 = load_dataset(V4_PATH, log_transform=False) if USE_V4 else pd.DataFrame()

print(f"📊 V0 (synthetic): {len(df_synth)}")
print(f"📊 V1 (manual/auto): {len(df_v1)}")
print(f"📊 V2 (scaled auto): {len(df_v2)}")
print(f"📊 V3 (poisoned): {len(df_v3)}")
print(f"📊 V4 (safe): {len(df_v4)}")

# =============================
# REMOVE UNUSED COLUMNS
# =============================
DROP_COLS = ["prediction", "confidence", "decision", "risk_probability"]

for df_temp in [df_synth, df_v1, df_v2, df_v3, df_v4]:
    df_temp.drop(columns=DROP_COLS, errors="ignore", inplace=True)

# =============================
# ENSURE FEATURE CONSISTENCY 🔥
# =============================
ALL_FEATURES = [
    "wallet_age_days",
    "avg_tx",
    "recent_tx",
    "tx_frequency",
    "tx_per_min",
    "tx_per_hour",
    "tx_per_day",
    "avg_time_between_tx_sec",

    # V3 FEATURES
    "dust_tx_ratio",
    "similarity_hits",
    "new_sender_ratio",
    "is_poisoned_pattern"
]

def ensure_features(df):
    if df.empty:
        return df
    for col in ALL_FEATURES:
        if col not in df.columns:
            df[col] = 0
    return df

df_synth = ensure_features(df_synth)
df_v1 = ensure_features(df_v1)
df_v2 = ensure_features(df_v2)
df_v3 = ensure_features(df_v3)
df_v4 = ensure_features(df_v4)

# =============================
# COMBINE DATASETS 🔥
# =============================
df = pd.concat([df_synth, df_v1, df_v2, df_v3, df_v4], ignore_index=True)

print(f"\n📊 TOTAL TRAINING ROWS: {len(df)}")

# =============================
# FEATURES / LABEL
# =============================
X = df[ALL_FEATURES]
y = df["label"]  # 0 = normal, 1 = malicious, 2 = poisoned

# =============================
# SMART WEIGHTING 🔥
# =============================
weights = np.concatenate([

    # V0 → weakest (synthetic)
    np.ones(len(df_synth)) * 0.8,

    # V1 → strongest truth (manual/verified)
    np.ones(len(df_v1)) * 6.0,

    # V2 → semi-trusted auto labels
    np.ones(len(df_v2)) * 2.5 if USE_V2 else np.array([]),

    # V3 → poisoning is rare → boost hard
    np.ones(len(df_v3)) * 4.0 if USE_V3 else np.array([]),

    # V4 → safe but strict → medium trust
    np.ones(len(df_v4)) * 3.0 if USE_V4 else np.array([])
])

print("\n⚖️ Weights (PRIORITIZED):")
print(f" - V0 synthetic: {len(df_synth)} (0.8x)")
print(f" - V1 manual: {len(df_v1)} (6.0x)")
if USE_V2:
    print(f" - V2 auto: {len(df_v2)} (2.5x)")
if USE_V3:
    print(f" - V3 poisoned: {len(df_v3)} (4.0x)")
if USE_V4:
    print(f" - V4 safe: {len(df_v4)} (3.0x)")

# =============================
# SCALE FEATURES
# =============================
from sklearn.preprocessing import StandardScaler

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# =============================
# TRAIN MODEL 🔥 (IMPROVED)
# =============================
from sklearn.ensemble import RandomForestClassifier

model = RandomForestClassifier(
    n_estimators=300,
    max_depth=14,
    min_samples_split=5,
    class_weight="balanced",   # 🔥 critical
    random_state=42,
    n_jobs=-1
)

model.fit(X_scaled, y, sample_weight=weights)

# =============================
# SAVE MODEL
# =============================
pickle.dump(model, open(MODEL_PATH, "wb"))
pickle.dump(scaler, open(SCALER_PATH, "wb"))
pickle.dump(ALL_FEATURES, open(FEATURE_PATH, "wb"))

print(f"\n🔥 {TOKEN.upper()} MODEL TRAINED & SAVED")

# =============================
# QUICK TEST
# =============================
sample = X.iloc[0:1]
probs = model.predict_proba(scaler.transform(sample))[0]

print("\n🔥 Sample Prediction:")
print(f"Normal: {probs[0]:.4f}")
print(f"Malicious: {probs[1]:.4f}")
print(f"Poisoned: {probs[2]:.4f}")