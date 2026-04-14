import pandas as pd
import numpy as np
import pickle
import os

# =============================
# CONFIG 🔥 MULTI-TOKEN
# =============================
TOKEN = "all"  # 🔥 Change to: "all" (train all tokens) or specific token: "usdt", "usdc", "busd", "dai", "usdp", "tusd"
TRAIN_ESTIMATORS = 150
TRAIN_MAX_DEPTH = 14
TRAIN_N_JOBS = 1

# Available tokens
AVAILABLE_TOKENS = ["usdt", "usdc", "busd", "dai", "usdp", "tusd"]

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


def load_dataset_with_info(path, log_transform=True):
    df = load_dataset(path, log_transform=log_transform)
    if os.path.exists(path) and df.empty:
        print(f"⚠️ {os.path.basename(path)} exists but contains no valid labeled rows and will be skipped.")
    return df

# =============================
# FEATURES CONSISTENCY
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

# =============================
# TRAINING FUNCTION 🔥
# =============================
def train_token_model(token):
    print(f"\n{'='*60}")
    print(f"🚀 TRAINING {token.upper()} MODEL")
    print(f"{'='*60}")
    
    # Build file paths
    SYNTHETIC_PATH = f"datasets/{token}_training_ready.csv"  # from cleaner.py
    V1_PATH = f"datasets/v1_{token}.csv"  # from main.py extract (Etherscan auto-labeled)
    V2_PATH = f"datasets/v2_{token}.csv"  # from main.py extract (Etherscan auto-labeled)
    V3_PATH = f"datasets/v3_{token}.csv"  # from main.py extract (poisoning detected)
    V4_PATH = f"datasets/{token}_labeled_v4.csv"  # from v4_script.py (safe wallets)
    
    MODEL_PATH = f"models/{token}_model.pkl"
    SCALER_PATH = f"models/{token}_scaler.pkl"
    FEATURE_PATH = f"models/{token}_features.pkl"
    
    # Check which files exist
    missing_versions = []
    version_files = {
        "V0 (Synthetic)": SYNTHETIC_PATH,
        "V1 (Manual/Auto)": V1_PATH,
        "V2 (Scaled Auto)": V2_PATH,
        "V3 (Poisoned)": V3_PATH,
        "V4 (Safe)": V4_PATH
    }
    
    for version_name, version_path in version_files.items():
        if not os.path.exists(version_path):
            missing_versions.append(version_name)
    
    if missing_versions:
        print(f"\n⚠️ MISSING VERSIONS:")
        for missing in missing_versions:
            print(f"   - {missing}")
    
    # Load datasets
    df_synth = load_dataset_with_info(SYNTHETIC_PATH) if os.path.exists(SYNTHETIC_PATH) else pd.DataFrame()
    df_v1 = load_dataset_with_info(V1_PATH) if os.path.exists(V1_PATH) else pd.DataFrame()
    df_v2 = load_dataset_with_info(V2_PATH, log_transform=False) if os.path.exists(V2_PATH) else pd.DataFrame()
    df_v3 = load_dataset_with_info(V3_PATH, log_transform=False) if os.path.exists(V3_PATH) else pd.DataFrame()
    df_v4 = load_dataset_with_info(V4_PATH, log_transform=False) if os.path.exists(V4_PATH) else pd.DataFrame()
    
    print(f"\n📊 DATA LOADED:")
    print(f"   - V0 (synthetic): {len(df_synth)} rows")
    print(f"   - V1 (manual/auto): {len(df_v1)} rows")
    print(f"   - V2 (scaled auto): {len(df_v2)} rows")
    print(f"   - V3 (poisoned): {len(df_v3)} rows")
    print(f"   - V4 (safe): {len(df_v4)} rows")
    
    # Remove unused columns
    DROP_COLS = ["prediction", "confidence", "decision", "risk_probability"]
    for df_temp in [df_synth, df_v1, df_v2, df_v3, df_v4]:
        df_temp.drop(columns=DROP_COLS, errors="ignore", inplace=True)
    
    # Ensure features
    df_synth = ensure_features(df_synth)
    df_v1 = ensure_features(df_v1)
    df_v2 = ensure_features(df_v2)
    df_v3 = ensure_features(df_v3)
    df_v4 = ensure_features(df_v4)
    
    # Combine datasets
    df = pd.concat([df_synth, df_v1, df_v2, df_v3, df_v4], ignore_index=True)
    print(f"\n📊 TOTAL TRAINING ROWS: {len(df)}")
    
    # Check if we have enough data
    if len(df) == 0:
        print(f"\n❌ ERROR: No training data available for {token.upper()}")
        print(f"   At least V1 (manual/auto) data is required for training.")
        return
    
    # Features and labels
    X = df[ALL_FEATURES]
    y = df["label"]
    
    class_counts = y.value_counts().to_dict()
    print("\n🧠 LABEL DISTRIBUTION:")
    for cls, count in class_counts.items():
        print(f"   - {cls}: {count}")
    
    if len(class_counts) < 2:
        print(f"\n❌ ERROR: Not enough label classes for {token.upper()} training")
        print("   Need at least 2 label classes. Skipping this token.")
        return
    
    # Smart weighting - dynamically build based on what's available
    weights = []
    
    if len(df_synth) > 0:
        weights.extend(np.ones(len(df_synth)) * 0.8)
    if len(df_v1) > 0:
        weights.extend(np.ones(len(df_v1)) * 6.0)
    if len(df_v2) > 0:
        weights.extend(np.ones(len(df_v2)) * 2.5)
    if len(df_v3) > 0:
        weights.extend(np.ones(len(df_v3)) * 4.0)
    if len(df_v4) > 0:
        weights.extend(np.ones(len(df_v4)) * 3.0)
    
    weights = np.array(weights)
    
    print("\n⚖️ WEIGHTS (PRIORITIZED):")
    if len(df_synth) > 0:
        print(f"   - V0 (synthetic): {len(df_synth)} rows (0.8x)")
    if len(df_v1) > 0:
        print(f"   - V1 (manual): {len(df_v1)} rows (6.0x)")
    if len(df_v2) > 0:
        print(f"   - V2 (auto): {len(df_v2)} rows (2.5x)")
    if len(df_v3) > 0:
        print(f"   - V3 (poisoned): {len(df_v3)} rows (4.0x)")
    if len(df_v4) > 0:
        print(f"   - V4 (safe): {len(df_v4)} rows (3.0x)")
    
    # Scale features
    from sklearn.preprocessing import StandardScaler
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Train model
    from sklearn.ensemble import RandomForestClassifier
    model = RandomForestClassifier(
        n_estimators=TRAIN_ESTIMATORS,
        max_depth=TRAIN_MAX_DEPTH,
        min_samples_split=5,
        class_weight="balanced",
        random_state=42,
        n_jobs=TRAIN_N_JOBS
    )
    
    try:
        model.fit(X_scaled, y, sample_weight=weights)
    except Exception as e:
        print(f"\n❌ ERROR: Failed training {token.upper()} model: {e}")
        return
    
    # Save model
    os.makedirs("models", exist_ok=True)
    pickle.dump(model, open(MODEL_PATH, "wb"))
    pickle.dump(scaler, open(SCALER_PATH, "wb"))
    pickle.dump(ALL_FEATURES, open(FEATURE_PATH, "wb"))
    
    print(f"\n🔥 {token.upper()} MODEL TRAINED & SAVED")
    
    # Quick test
    sample = X.iloc[0:1]
    probs = model.predict_proba(scaler.transform(sample))[0]
    
    class_names = {
        0: "Normal",
        1: "Malicious",
        2: "Poisoned",
        -1: "Unknown"
    }

    print("\n🔥 Sample Prediction:")
    for cls, prob in zip(model.classes_, probs):
        label = class_names.get(cls, f"Class {cls}")
        print(f"{label}: {prob:.4f}")
    print()

# =============================
# MAIN EXECUTION 🔥
# =============================
if __name__ == "__main__":
    if TOKEN.lower() == "all":
        print("\n" + "="*60)
        print("🔥 TRAINING ALL TOKENS")
        print("="*60)
        for token in AVAILABLE_TOKENS:
            try:
                train_token_model(token)
            except Exception as e:
                print(f"\n❌ ERROR: {token.upper()} model failed with exception: {e}")
                continue
        print("\n" + "="*60)
        print("✅ ALL TOKENS DONE")
        print("="*60)
    else:
        train_token_model(TOKEN.lower())