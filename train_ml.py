import argparse

import pandas as pd

import numpy as np

import pickle

import os



# =============================

# CONFIG ? MULTI-TOKEN

# =============================

TOKEN = "all"  # ? Change to: "all" (train all tokens) or specific token: "usdt", "usdc", "busd", "dai", "usdp", "tusd"

TRAIN_ESTIMATORS = 150

TRAIN_MAX_DEPTH = 14

TRAIN_N_JOBS = 1



# Available tokens

AVAILABLE_TOKENS = ["usdt", "usdc", "busd", "dai", "usdp", "tusd"]



# =============================

# LOAD FUNCTION ? (SAFE)

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



        # [OK] SAFE LOG TRANSFORM (prevents double log)

        if log_transform and df["avg_tx"].max() > 50:

            df["avg_tx"] = np.log1p(df["avg_tx"])

            df["recent_tx"] = np.log1p(df["recent_tx"])



        return df



    except Exception as e:

        print(f"[WARN] Failed loading {path}: {e}")

        return pd.DataFrame()





def load_dataset_with_info(path, log_transform=True):

    df = load_dataset(path, log_transform=log_transform)

    if os.path.exists(path) and df.empty:

        print(f"[WARN] {os.path.basename(path)} exists but contains no valid labeled rows and will be skipped.")

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

    "is_poisoned_pattern",

    "tiny_tx_count",

    "unique_receivers",

    "avg_tx_value",

    "window_days",

    "repeat_small_to_count",

    "no_meaningful_flow",

    "short_time_window"

]



def ensure_features(df):

    if df.empty:

        return df

    for col in ALL_FEATURES:

        if col not in df.columns:

            df[col] = 0

    return df



# =============================

# TRAINING FUNCTION ?

# =============================

def train_token_model(token, model_choice="auto"):

    print(f"\n{'='*60}")

    print(f"? TRAINING {token.upper()} MODEL")

    print(f"{'='*60}")

    

    # Build file paths

    SYNTHETIC_PATH = f"datasets/{token}_training_ready.csv"  # from cleaner.py

    V1_PATH = f"datasets/v1_{token}.csv"  # from main.py extract (Etherscan auto-labeled)

    V2_PATH = f"datasets/v2_{token}.csv"  # from main.py extract (Etherscan auto-labeled)

    V3_PATH = f"datasets/v3_{token}.csv"  # from main.py extract (poisoning detected)

    V4_PATH = f"datasets/{token}_labeled_v4.csv"  # from v4_script.py (safe wallets)

    # NOTE: main.py also generates v3_raw_{token}.csv and {token}_labeled_v3.csv for diagnostics,

    # but training currently consumes datasets/v3_{token}.csv.

    

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

        print(f"\n[WARN] MISSING VERSIONS:")

        for missing in missing_versions:

            print(f"   - {missing}")

    

    # Load datasets

    df_synth = load_dataset_with_info(SYNTHETIC_PATH) if os.path.exists(SYNTHETIC_PATH) else pd.DataFrame()

    df_v1 = load_dataset_with_info(V1_PATH) if os.path.exists(V1_PATH) else pd.DataFrame()

    df_v2 = load_dataset_with_info(V2_PATH, log_transform=False) if os.path.exists(V2_PATH) else pd.DataFrame()

    df_v3 = load_dataset_with_info(V3_PATH, log_transform=False) if os.path.exists(V3_PATH) else pd.DataFrame()

    df_v4 = load_dataset_with_info(V4_PATH, log_transform=False) if os.path.exists(V4_PATH) else pd.DataFrame()

    

    print(f"\n? DATA LOADED:")

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

    # [CRITICAL] Filter out label=-1 (unlabeled rows) - XGBoost requires consecutive class indices [0,1,2]

    df = df[df["label"] != -1].reset_index(drop=True)

    print(f"\n? TOTAL TRAINING ROWS: {len(df)} (after filtering unlabeled)")

    

    # Check if we have enough data

    if len(df) == 0:

        print(f"\n[ERROR] ERROR: No training data available for {token.upper()}")

        print(f"   At least V1 (manual/auto) data is required for training.")

        return

    

    # Features and labels

    X = df[ALL_FEATURES]

    y = df["label"]

    

    class_counts = y.value_counts().to_dict()

    print("\n? LABEL DISTRIBUTION:")

    for cls, count in class_counts.items():

        print(f"   - {cls}: {count}")

    

    if len(class_counts) < 2:

        print(f"\n[ERROR] ERROR: Not enough label classes for {token.upper()} training")

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

    

    print("\n?? WEIGHTS (PRIORITIZED):")

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



    # =============================

    # HANDLE CLASS IMBALANCE: OVERSAMPLE MINORITY CLASSES

    # =============================

    # Many samples are labeled -1 (unknown); focus on clear labels (0, 1, 2)

    from sklearn.utils import resample

    

    labeled_indices = y[y != -1].index.tolist()  # Keep only labeled samples

    unknown_indices = y[y == -1].index.tolist()  # Set aside unknown (-1) samples

    

    # Oversample minority malicious/poisoned classes to balance training

    if len(labeled_indices) > 0:

        X_labeled = X_scaled[labeled_indices]

        y_labeled = y[labeled_indices]

        

        # Identify safe (0) and risk (1, 2) samples

        safe_idx = [i for i, idx in enumerate(labeled_indices) if y.iloc[idx] == 0]

        risk_idx = [i for i, idx in enumerate(labeled_indices) if y.iloc[idx] in [1, 2]]

        

        # Oversample risk classes if too few

        if len(risk_idx) > 0 and len(safe_idx) > len(risk_idx) * 3:

            # Duplicate risk samples to improve balance

            target_risk = len(safe_idx) // 3  # Set risk to ~1/3 of safe

            if len(risk_idx) < target_risk:

                boost_amount = target_risk - len(risk_idx)

                sampled_indices = resample(risk_idx, n_samples=len(risk_idx) + boost_amount, random_state=42)

                oversampled_indices_local = safe_idx + sampled_indices

                X_labeled = np.vstack([X_labeled[i] for i in oversampled_indices_local])

                y_labeled = pd.Series([y_labeled.iloc[i] for i in oversampled_indices_local]).reset_index(drop=True)

        

        # Append unknown samples (lower weight) for supplementary learning

        if len(unknown_indices) > 0:

            X_unknown = X_scaled[[i for i, idx in enumerate(range(len(X_scaled))) if idx in unknown_indices]]

            y_unknown = y[unknown_indices].reset_index(drop=True)

            X_train_combined = np.vstack([X_labeled, X_unknown])

            y_train_combined = pd.concat([y_labeled, y_unknown], ignore_index=True)

        else:

            X_train_combined = X_labeled

            y_train_combined = y_labeled

    else:

        X_train_combined = X_scaled

        y_train_combined = y



    # Train / compare multiple models (RandomForest, XGBoost, LightGBM if available)

    from sklearn.model_selection import train_test_split

    from sklearn.metrics import f1_score



    sample_weight = weights if (isinstance(weights, np.ndarray) and len(weights) == len(df)) else None



    # Stratified split when possible

    try:

        if sample_weight is not None:

            X_train, X_val, y_train, y_val, w_train, w_val = train_test_split(X_train_combined, y_train_combined, sample_weight, test_size=0.2, stratify=y_train_combined, random_state=42)

        else:

            X_train, X_val, y_train, y_val = train_test_split(X_train_combined, y_train_combined, test_size=0.2, stratify=y_train_combined, random_state=42)

            w_train = w_val = None

    except Exception:

        # fallback without stratify

        if sample_weight is not None:

            X_train, X_val, y_train, y_val, w_train, w_val = train_test_split(X_train_combined, y_train_combined, sample_weight, test_size=0.2, random_state=42)

        else:

            X_train, X_val, y_train, y_val = train_test_split(X_train_combined, y_train_combined, test_size=0.2, random_state=42)

            w_train = w_val = None



    models = {}

    # RandomForest baseline

    from sklearn.ensemble import RandomForestClassifier

    models['rf'] = RandomForestClassifier(

        n_estimators=TRAIN_ESTIMATORS,

        max_depth=TRAIN_MAX_DEPTH,

        min_samples_split=5,

        class_weight="balanced",

        random_state=42,

        n_jobs=TRAIN_N_JOBS

    )



    # Try XGBoost

    try:

        from xgboost import XGBClassifier

        models['xgb'] = XGBClassifier(

            n_estimators=200,

            max_depth=6,

            use_label_encoder=False,

            eval_metric='mlogloss',

            random_state=42,

            n_jobs=TRAIN_N_JOBS

        )

    except Exception as e:

        print(f"[WARN] xgboost not available: {e}")



    # Try LightGBM

    try:

        from lightgbm import LGBMClassifier

        models['lgb'] = LGBMClassifier(

            n_estimators=200,

            random_state=42,

            n_jobs=TRAIN_N_JOBS

        )

    except Exception as e:

        print(f"[WARN] lightgbm not available: {e}")



    # If user requested a specific model, restrict candidates (if available)

    requested = str(model_choice).lower() if model_choice is not None else "auto"

    if requested in ("rf", "xgb", "lgb"):

        if requested not in models:

            print(f"[WARN] Requested model '{requested}' not available; continuing with available: {list(models.keys())}")

        else:

            models = {requested: models[requested]}



    best_score = -1

    best_name = None

    best_model = None



    for name, m in models.items():

        print(f"\n? Training {name} ...")

        try:

            # [FIXED] Removed early_stopping_rounds - not supported in sklearn XGBoost/LightGBM wrappers

            if w_train is not None:

                m.fit(X_train, y_train, sample_weight=w_train)

            else:

                m.fit(X_train, y_train)

        except Exception as e:

            error_msg = str(e).lower()

            print(f"[WARN] {name} failed: {e}")

            # Skip this model on class/type errors

            if "class" in error_msg or "expected" in error_msg or "inferred" in error_msg:

                print(f"   [WARN] Skipping {name} due to incompatible data/classes")

                continue

            else:

                continue



        preds = m.predict(X_val)

        try:

            score = f1_score(y_val, preds, average='macro')

        except Exception as e:

            print(f"[WARN] scoring failed for {name}: {e}")

            score = -1

        print(f"   - F1 (macro): {score:.4f}")



        if score > best_score:

            best_score = score

            best_name = name

            best_model = m



    if best_model is None:

        print("[ERROR] No model trained successfully; aborting.")

        return



    # Save best model (and a named copy)

    os.makedirs("models", exist_ok=True)

    pickle.dump(best_model, open(MODEL_PATH, "wb"))

    pickle.dump(best_model, open(f"models/{token}_model_{best_name}.pkl", "wb"))

    pickle.dump(scaler, open(SCALER_PATH, "wb"))

    pickle.dump(ALL_FEATURES, open(FEATURE_PATH, "wb"))



    print(f"\n? Best model: {best_name} (F1_macro: {best_score:.4f}) saved to {MODEL_PATH} and models/{token}_model_{best_name}.pkl")



    # Quick test / sample prediction

    sample = X.iloc[0:1]

    try:

        scaled_sample = scaler.transform(sample)

        if hasattr(best_model, 'predict_proba'):

            probs = best_model.predict_proba(scaled_sample)[0]

            classes_attr = getattr(best_model, 'classes_', None)

            if classes_attr is None:

                classes_attr = np.unique(y)

            class_names = {0: "Normal", 1: "Malicious", 2: "Poisoned", -1: "Unknown"}

            print("\n? Sample Prediction:")

            if len(probs) == len(classes_attr):

                for cls, prob in zip(classes_attr, probs):

                    label = class_names.get(cls, f"Class {cls}")

                    print(f"{label}: {prob:.4f}")

            else:

                print("   - classes/probs mismatch; skipping probability breakdown.")

        else:

            pred = best_model.predict(scaled_sample)[0]

            class_names = {0: "Normal", 1: "Malicious", 2: "Poisoned", -1: "Unknown"}

            print("\n? Sample Prediction (label):")

            print(class_names.get(pred, pred))

    except Exception as e:

        print(f"[WARN] Sample prediction failed: {e}")



# =============================

# MAIN EXECUTION ?

# =============================

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Train token models. Use --model to pick a specific estimator or 'auto' to compare.")

    parser.add_argument("--model", choices=["auto", "rf", "xgb", "lgb"], default="auto", help="Model choice: auto (compare), rf, xgb, lgb")

    parser.add_argument("--token", default=TOKEN, help="Token to train (e.g. usdt) or 'all' to train all tokens")

    args = parser.parse_args()



    model_choice = args.model

    token_arg = args.token.lower()



    if token_arg == "all":

        print("\n" + "="*60)

        print("? TRAINING ALL TOKENS")

        print("="*60)

        for token in AVAILABLE_TOKENS:

            try:

                train_token_model(token, model_choice=model_choice)

            except Exception as e:

                print(f"\n[ERROR] ERROR: {token.upper()} model failed with exception: {e}")

                continue

        print("\n" + "="*60)

        print("[OK] ALL TOKENS DONE")

        print("="*60)

    else:

        train_token_model(token_arg, model_choice=model_choice)