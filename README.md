# Real-Time Stablecoin Payout Risk Scoring System

## System Status: ✅ COMPLETE WITH DEFENSES

**Current capabilities:**
- 57 dataset CSVs (V0–V4 per token, ~5K rows each)
- 28 model artifacts (best RF/XGB/LGB per token)
- **Rule-based heuristics** for high-risk pattern detection
- **Weighted training** emphasizing high-quality labels (V1=6.0x, V3=4.0x)
- **Class imbalance handling** via oversampling minority classes
- **3-class decisions**: ALLOW, REVIEW, BLOCK

## Overview

This repository contains a multi-stage workflow for building a wallet risk scoring system for stablecoin activity on Ethereum. It is designed to collect wallet pools, extract behavioral features, generate labeled datasets across multiple risk versions, train token-specific machine learning models, and score wallets in real time.

The pipeline is organized around five dataset/version categories:

- `v0` — broad baseline safe wallets
- `v1` — high-trust malicious wallets (manual or auto-labeled)
- `v2` — scaled malicious wallet expansion
- `v3` — poisoning behavior detection
- `v4` — high-confidence safe wallets

## Project Goals

- Expand wallet networks from seed wallets using Etherscan transaction graphs
- Extract per-wallet, per-token features for stablecoins
- Auto-label suspicious wallets with keyword scraping and poisoning heuristics
- Train token-specific risk models for stablecoins: `USDT`, `USDC`, `BUSD`, `DAI`, `USDP`, `TUSD`
- Provide a runtime scoring module that can fetch transactions, build features, and classify wallets as `ALLOW`, `REVIEW`, or `BLOCK`

## Repository Structure and Folder Overview

```
Real-Time Stablecoin Payout Risk Scoring System/
│
├── main.py                          # Core dataset generation engine
├── train_ml.py                      # Multi-model ML training pipeline
├── wallet_check.py                  # Real-time wallet scoring inference
├── db.py                            # Database feature/label caching
├── model_tester.py                  # Sanity check / example script
├── scan_and_report.py               # Quick inventory of datasets/models
├── requirements.txt                 # Python dependencies (including optional boosters)
├── README.md                        # This file
│
├── datasets/                        # Generated training datasets (57 CSVs)
│   ├── v0_usdt.csv
│   ├── v0_usdc.csv
│   ├── v1_usdt.csv
│   ├── v1_usdc.csv
│   ├── v3_usdt.csv                  # Poisoned wallets (auto-labeled)
│   ├── v3_raw_usdt.csv              # All poisoning candidates (diagnostic)
│   ├── v3_clean_usdt.csv            # Confirmed poisoned only (diagnostic)
│   ├── v4_usdt.csv                  # High-confidence safe
│   ├── usdt_training_ready.csv      # V0 aggregated for training seed
│   ├── usdt_labeled_v4.csv          # V4 safe for training
│   ├── usdt_labeled_v3.csv          # V3 labeled for training
│   └── ... (one set per token: USDT, USDC, BUSD, DAI, USDP, TUSD)
│
├── models/                          # Trained model artifacts (28 PKL files)
│   ├── usdt_model.pkl               # Best trained model (RF/XGB/LGB)
│   ├── usdt_model_rf.pkl            # RandomForest variant
│   ├── usdt_model_xgb.pkl           # XGBoost variant (if available)
│   ├── usdt_model_lgb.pkl           # LightGBM variant (if available)
│   ├── usdt_scaler.pkl              # StandardScaler for feature normalization
│   ├── usdt_features.pkl            # Feature column metadata
│   └── ... (one set per token: USDT, USDC, BUSD, DAI, USDP, TUSD)
│
├── public address dataset/          # Wallet pool CSVs (persisted state)
│   ├── v0_wallet_pool.csv           # V0 expanded wallets (~4000)
│   ├── v1_wallet_pool.csv           # V1 expanded wallets (~2000)
│   ├── v2_wallet_pool.csv           # V2 expanded wallets (~5000)
│   ├── v3_wallet_pool.csv           # V3 expanded wallets (~6000)
│   └── v4_wallet_pool.csv           # V4 expanded wallets (~2500)
│
├── backups/                         # Historical dataset backups
│   └── *_datasets.csv_*.csv
│
└── .venv/                           # Python virtual environment (created by user)
```

## File and Folder Descriptions

### Files

#### `main.py` — Core Dataset Generation Engine

**What it does:**
This is the heart of the data pipeline. It expands wallet networks from seed addresses using Etherscan transaction graphs and extracts behavioral features for each wallet. It orchestrates V0–V4 dataset generation across all stablecoin tokens.

**Key features:**
- Three execution modes: `expand` (grow wallet pools), `extract` (compute features), `dual` (both)
- Parallel subprocess spawning for each version to maximize efficiency
- Token filtering: generates per-token datasets for USDT, USDC, BUSD, DAI, USDP, TUSD
- Etherscan API integration with rate limiting and retry logic
- Automatic keyword scraping for malicious labels (V1/V2)
- Poisoning heuristic detection (V3)
- Safety filtering (V0/V4)

**Output:**
- 57 CSV files in `datasets/` (V0–V4 per token, training-ready aggregates)
- 5 wallet pool CSVs in `public address dataset/` (reusable state for future runs)

**Configuration:**
```python
SEEDS_V0 = ["0x..."]              # Edit these per version
SEEDS_V1 = ["0x..."]
ENABLE_V0 = True                  # Toggle which versions to run
MODE_RUN = "dual"                 # "expand", "extract", or "dual"
```

#### `train_ml.py` — Multi-Model ML Training Pipeline

**What it does:**
Reads all v0–v4 CSV datasets from `datasets/` and trains machine learning models. It builds weighted training sets, splits into train/validation, trains three model types (RandomForest, XGBoost, LightGBM), compares their performance, and saves the best model.

**Key features:**
- Multi-model support: RandomForest (always), XGBoost (optional), LightGBM (optional)
- Weighted training strategy (see "Weighting Strategy" section below)
- Stratified train/validation split (80/20)
- Early stopping for gradient boosters
- Macro F1 score evaluation
- Automatic model selection by performance
- Feature consistency checks across datasets

**Output:**
- Per-token model artifacts (5 files each):
  - `models/<token>_model.pkl` (best model)
  - `models/<token>_model_rf.pkl`, `_xgb.pkl`, `_lgb.pkl` (named copies)
  - `models/<token>_scaler.pkl` (feature StandardScaler)
  - `models/<token>_features.pkl` (feature column list)

**CLI Usage:**
```powershell
python train_ml.py --model auto --token all		# All tokens, best model
python train_ml.py --model rf --token usdt		# RandomForest only, USDT
python train_ml.py --model xgb --token all		# XGBoost only, all tokens
```

#### `wallet_check.py` — Real-Time Wallet Scoring Inference

**What it does:**
Loads trained models and scalers, then scores wallet addresses. It fetches transactions from Etherscan, generates runtime features, and applies the trained model to classify risk.

**Key features:**
- Database cache lookup (fast path)
- Etherscan API fallback (live data)
- Automatic token detection
- Runtime feature generation matching training schema
- 3-class decision logic: ALLOW, REVIEW, BLOCK
- Timing instrumentation

**Output:**
- Interactive wallet scoring with probabilities and decision
- Example:
  ```
  Wallet: 0x14d2595fecbdd884035900c85ce56afbbec6c745
  Token: USDT
  Normal: 0.7893
  Malicious: 0.2036
  Poisoned: 0.0000
  Decision: ALLOW
  Reason: Low risk
  ⏱ TOTAL TIME: 0.123s
  ```

#### `db.py` — Database Feature and Label Caching

**What it does:**
Provides optional PostgreSQL database integration for caching extracted features and storing wallet labels. This accelerates repeated scoring of the same wallet.

**Key functions:**
- `get_features(wallet, token)` — retrieve cached features (instant)
- `save_features(wallet, token, f)` — store extracted features
- `get_label(wallet)` — fetch stored label metadata
- `save_label(wallet, label, trusted)` — persist label

**Note:**
- If `DATABASE_URL` env var is missing, all functions become no-ops (graceful degradation)
- DB is optional; the system works without it but will be slower

#### `scan_and_report.py` — Quick Inventory Tool

**What it does:**
Scans `datasets/` and `models/` directories and prints a summary of available files and row counts.

**Output:**
```
Dataset report:
  - v0_usdt.csv: 428 rows
  - v1_usdt.csv: 81 rows
  - v3_usdt.csv: 3894 rows
  - v4_usdt.csv: 242 rows
  - usdt_training_ready.csv: 428 rows
  ...
Model artifacts:
  - usdt_model.pkl
  - usdt_scaler.pkl
  - usdt_features.pkl
  ...
```

#### `model_tester.py` — Example/Sanity Check Script

**What it does:**
A standalone example that loads the USDT model and makes a test prediction. Useful for verifying that model loading works before full inference.

#### `requirements.txt` — Python Dependencies

**Contents:**
```
pandas>=1.3
numpy>=1.21
requests>=2.26
beautifulsoup4>=4.9
scikit-learn>=1.0
psycopg2-binary>=2.9
python-dotenv>=0.19
xgboost>=1.5          # Optional booster
lightgbm>=3.3         # Optional booster
```

### Folders

#### `datasets/` — Generated Training Datasets

**Contents:** 57 CSV files generated by `main.py`

**Organization:**
- **Per-version:** `v0_<token>.csv`, `v1_<token>.csv`, etc.
- **Training aggregates:** `<token>_training_ready.csv` (V0 rolled up)
- **Diagnostic:** `v3_raw_<token>.csv`, `v3_clean_<token>.csv` (poisoning breakdowns)

**Key files for training:**
```
datasets/
├── v0_usdt.csv                    ← Safe baseline (428 rows for USDT)
├── v1_usdt.csv                    ← Malicious (81 rows)
├── v3_usdt.csv                    ← Poisoned (3894 rows)
├── v4_usdt.csv                    ← High-confidence safe (242 rows)
└── ... (repeat for USDC, BUSD, DAI, USDP, TUSD)
```

**Row counts per token (example USDT):**
- V0: 428
- V1: 81
- V3: 3894
- V4: 242
- **Total trainable:** 4645 rows per token

#### `models/` — Trained Model Artifacts

**Contents:** 28 PKL files (5 per token × 6 tokens)

**Naming convention:**
- `<token>_model.pkl` — **Primary** (best model, loaded by `wallet_check.py`)
- `<token>_model_rf.pkl` — RandomForest copy (for reference)
- `<token>_model_xgb.pkl` — XGBoost copy (if best)
- `<token>_model_lgb.pkl` — LightGBM copy (if best)
- `<token>_scaler.pkl` — StandardScaler (feature normalization)
- `<token>_features.pkl` — Feature column names

#### `public address dataset/` — Persisted Wallet Pools

**Contents:** 5 CSV files (one per version)

**Purpose:**
Saves expanded wallet pools for reuse. If you run `main.py --mode extract` next time with `USE_POOL_V* = True`, it will use these pools instead of re-expanding from seeds.

**Typical sizes:**
- v0_wallet_pool.csv: ~4000 wallets
- v1_wallet_pool.csv: ~2000 wallets
- v2_wallet_pool.csv: ~5000 wallets
- v3_wallet_pool.csv: ~6000 wallets
- v4_wallet_pool.csv: ~2500 wallets

#### `backups/` — Historical Dataset Snapshots

**Contents:** Old CSV files (timestamped or versioned)

**Purpose:** Safety archive in case you need to revert to earlier datasets.

## Version Definitions and What They Mean

### `v0` — Broad Baseline Safe

- Collects wallets from baseline seed addresses
- Extracts features and retains candidates that pass safety heuristics
- Label: `0`
- Produces `datasets/v0_<token>.csv`
- Also generates `datasets/<token>_training_ready.csv`

### `v1` — High-Trust Malicious

- Expands from hand-picked malicious seeds
- Extracts wallet features
- Auto-labels using Etherscan page keyword scraping
- Label is `1` if suspicious keywords are found, otherwise `None`

### `v2` — Scaled Malicious

- Similar to `v1` but designed for wider crawling and larger pools
- Expands network aggressively from multiple seed wallets
- Auto-labels with Etherscan keyword scraping

### `v3` — Poisoning Behavior Detection

- Targets address poisoning and spam-like behaviors
- Computes extra poisoning features:
  - `dust_tx_ratio`
  - `similarity_hits`
  - `new_sender_ratio`
  - `is_poisoned_pattern`
- Label: `2` for poisoned, `-1` otherwise
- Saves both raw and filtered datasets

### `v4` — High-Confidence Safe

- Builds on V0/V4 heuristics with stricter filtering
- Produces a limited set of very clean wallets
- Label: `0`
- Intended to provide strong safe examples for training

## Detailed Function Summary

### `main.py`

- `get_api_key(version)` — returns an API key for a specific version
- `parse_args()` — reads `--version` and `--mode` CLI flags
- `load_pool(path)` — loads saved wallet pool CSVs and discovers versioned alternatives
- `get_unique_path(path)` — generates a non-conflicting output path
- `save_pool(wallets, path)` — writes unique wallets to CSV
- `get_config_for_version(version)` — returns the per-version config structure
- `get_use_pool_for_version(version)` — returns pool-usage flag for a version
- `run_version_pipeline(version, mode)` — dispatches one version in a chosen mode
- `run_parallel_versions(mode)` — uses subprocesses to run enabled versions in parallel
- `fetch_txs(address, version, retry=2)` — fetches token transfers from Etherscan with retries and rate handling
- `expand_wallets(config, version, use_pool)` — expands a wallet graph from seeds or a saved pool
- `compute_base_features(txs, token_filter=None)` — computes base transaction behavior features
- `check_wallet_keywords(address)` — scrapes Etherscan page text for suspicious keywords
- `compute_v3_features(txs, wallet, config, token_filter=None)` — computes poisoning-specific metrics
- `is_v0_safe_candidate(row, wallet)` — enforces V0 safety filters
- `is_v4_high_confidence_candidate(row, wallet)` — enforces stricter V4 safety filters
- `run_v0()`, `run_v1()`, `run_v2()`, `run_v3()` — version-specific runner helpers
- `extract_features_for_version(config, version, use_pool)` — extracts all feature datasets for a version
- `generate_v4_dataset(token, max_v4=V4_MAX)` — builds V4 safe dataset per token
- `generate_v0_training_ready(token)` — generates V0 training-ready CSVs per token
- `run_v4()` — generates all token V4 datasets
- `_run_expand_mode()`, `_run_extract_mode()`, `_run_dual_mode()` — internal mode dispatch helpers

### `train_ml.py`

- `load_dataset(path, log_transform=True)` — loads CSV dataset safely, applies log transform when needed
- `load_dataset_with_info(path, log_transform=True)` — wrapper that logs missing/empty dataset info
- `ensure_features(df)` — adds missing feature columns with default values
- `train_token_model(token)` — loads all version files for a token, combines them, trains a weighted random forest, saves model and scaler

### `wallet_check.py`

- `classify_decision(prob_malicious, prob_poisoned, conf, features, low_data=False)` — final decision logic for `ALLOW`, `REVIEW`, `BLOCK`
- `fetch_transactions(address)` — Etherscan token transaction fetch for live inference
- `detect_token(transactions)` — selects the most frequent token observed in wallet transactions
- `generate_features(transactions)` — runtime feature builder for scoring
- `get_token_probabilities(model, scaled)` — extracts class probabilities for each model class
- `align_features_for_token(token, features)` — aligns runtime feature dict to model columns
- `score_wallet(address)` — end-to-end wallet risk scoring workflow

### `db.py`

- `get_features(wallet, token)` — retrieves cached features
- `save_features(wallet, token, f)` — writes feature cache rows
- `get_label(wallet)` — retrieves stored wallet label
- `save_label(wallet, label, trusted)` — stores label metadata

### `model_tester.py`

- Example model load and prediction script for USDT
- `classify_risk(prob)` — simple threshold-based decision helper

## Data Files and Naming Conventions

### Pools

- Saved wallet pools are stored under `public address dataset/`
- Pool file names:
  - `v0_wallet_pool.csv`
  - `v1_wallet_pool.csv`
  - `v2_wallet_pool.csv`
  - `v3_wallet_pool.csv`
  - `v4_wallet_pool.csv`
- Versioned backups are created automatically when collisions occur, e.g. `v0_T1wallet_pool.csv`

### Datasets

Generated dataset files are saved to `datasets/`:

- `v0_<token>.csv`
- `v1_<token>.csv`
- `v2_<token>.csv`
- `v3_raw_<token>.csv`
- `v3_clean_<token>.csv`
- `<token>_training_ready.csv`
- `<token>_labeled_v3.csv`
- `<token>_labeled_v4.csv`

### Models

Saved model artifacts are stored under `models/`:

- `<token>_model.pkl`
- `<token>_scaler.pkl`
- `<token>_features.pkl`

## Dependencies

This project depends on:

- Python 3.9+ (recommended)
- pandas
- numpy
- requests
- beautifulsoup4
- scikit-learn
- psycopg2
- python-dotenv

Install dependencies in the project virtual environment:

```powershell
python -m pip install pandas numpy requests beautifulsoup4 scikit-learn psycopg2-binary python-dotenv
```

## Complete Step-by-Step Quickstart

This section walks you through the **entire end-to-end system** in order.

### Prerequisites

1. Python 3.9+ installed
2. Create a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

3. Install dependencies:

```powershell
pip install pandas numpy requests beautifulsoup4 scikit-learn psycopg2-binary python-dotenv
```

4. (Optional) Install boosters for better model performance:

```powershell
pip install xgboost lightgbm
```

### Step 1: Configure Dataset Generation (main.py)

Edit `main.py` and customize:

- `SEEDS_V0`, `SEEDS_V1`, `SEEDS_V2`, `SEEDS_V3`, `SEEDS_V4` — wallet seed lists per version
- `ENABLE_V0` through `ENABLE_V4` — which versions to run (all `True` by default)
- `MODE_RUN = "dual"` — expand wallets, then extract features (recommended)

**What happens:**
- Expands wallet networks from seeds using Etherscan transaction graphs
- Extracts per-token features for USDT, USDC, BUSD, DAI, USDP, TUSD
- Auto-labels suspicious wallets using keyword scraping and poisoning heuristics
- **Generates ready-to-train CSVs** in `datasets/`:
  - `v0_<token>.csv` — baseline safe wallets
  - `v1_<token>.csv` — malicious wallets (auto-labeled)
  - `v3_<token>.csv` — poisoned wallets (auto-labeled)
  - `v4_<token>.csv` — high-confidence safe wallets
  - `<token>_training_ready.csv` — aggregated V0 training seed

### Step 2: Run Dataset Generation

```powershell
python main.py --mode dual
```

**Expected output:**
- Wallet pools saved to `public address dataset/v*_wallet_pool.csv`
- Dataset CSVs saved to `datasets/` (see above)
- Parallel processes spawn for each enabled version (V0–V4)
- Total time: ~10–30 minutes depending on API rate limits and pool sizes

**Alternative modes:**

```powershell
# Expand only (save wallet pools)
python main.py --mode expand

# Extract only (use existing pools)
python main.py --mode extract

# Run single version in extract mode
python main.py --version v3 --mode extract
```

### Step 3: Verify Generated Datasets

Before training, check that CSVs were created:

```powershell
python scan_and_report.py
```

**Expected output:**
- List of all CSV files in `datasets/` with row counts
- List of all model artifacts in `models/` (if any)
- Confirms v0, v1, v3, v4 CSVs exist per token

### Step 4: Train Machine Learning Models

**Now the CSVs generated in Step 2 are fed directly to training:**

```powershell
python train_ml.py --model auto --token all
```

**What happens:**
- Reads v0/v1/v3/v4 CSVs from `datasets/`
- Combines all rows with weighted importance:
  - V0 synthetic: 0.8x weight
  - V1 malicious: 6.0x weight (high priority)
  - V3 poisoned: 4.0x weight (high priority)
  - V4 safe: 3.0x weight
- Trains RandomForest, XGBoost, LightGBM (if installed)
- Compares models by macro F1 score on validation set
- **Saves best model** to:
  - `models/<token>_model.pkl` (primary)
  - `models/<token>_model_<name>.pkl` (named copy, e.g., `usdt_model_rf.pkl`)
  - `models/<token>_scaler.pkl`
  - `models/<token>_features.pkl`

**Expected output per token:**
```
============================================================
🚀 TRAINING USDT MODEL
============================================================
...
📊 TOTAL TRAINING ROWS: 4645
🧠 LABEL DISTRIBUTION:
   - -1: 3798 (unknown/spam)
   - 0: 670 (safe)
   - 1: 81 (malicious)
   - 2: 96 (poisoned)
...
🔧 Training rf ...
   - F1 (macro): 0.8329
🔧 Training xgb ...
   - F1 (macro): 0.8412
🔧 Training lgb ...
   - F1 (macro): 0.8250
🔥 Best model: xgb (F1_macro: 0.8412) saved to models/usdt_model.pkl and models/usdt_model_xgb.pkl
```

**Training options:**

```powershell
# Auto-select best model (RF/XGB/LGB) for all tokens (recommended)
python train_ml.py --model auto --token all

# Train only RandomForest for all tokens
python train_ml.py --model rf --token all

# Train all models for one token (USDT)
python train_ml.py --model auto --token usdt

# Train only XGBoost for USDC
python train_ml.py --model xgb --token usdc

# Train only LightGBM for DAI
python train_ml.py --model lgb --token dai
```

**Training time:** ~2–5 minutes for all tokens with auto selection

### Step 5: Score Wallets in Real-Time

With models trained, you can now score wallet addresses:

```powershell
python wallet_check.py
```

**Interactive usage:**

```
🔥 FINAL SYSTEM
Wallet: 0x14d2595fecbdd884035900c85ce56afbbec6c745

⚡ CACHE HIT (DB) → 0.123s
🔥 RESULT (DB)
Wallet: 0x14d2595fecbdd884035900c85ce56afbbec6c745
Token: USDT
Normal: 0.7893
Malicious: 0.2036
Poisoned: 0.0000
Decision: ALLOW
Reason: Low risk
⏱ TOTAL TIME: 0.123s

Wallet: 0x3D...  (enter another wallet or 'exit' to quit)
```

**Features:**
- Checks database cache first (fast)
- Falls back to Etherscan API if cache miss
- Auto-detects most frequent stablecoin token
- Outputs 3-class risk decision: `ALLOW`, `REVIEW`, or `BLOCK`

### Step 6: Test a Single Wallet (Non-Interactive)

```powershell
python -c "from wallet_check import score_wallet; score_wallet('0x14d2595fecbdd884035900c85ce56afbbec6c745')"
```

## Complete End-to-End Workflow Summary

| Step | Command | Input | Output | Time |
|------|---------|-------|--------|------|
| 1 | Edit `main.py` seeds | — | Config updated | — |
| 2 | `python main.py --mode dual` | Etherscan API | `datasets/*.csv` | 10–30 min |
| 3 | `python scan_and_report.py` | `datasets/` | CSV inventory | <1 sec |
| 4 | `python train_ml.py --model auto --token all` | `datasets/*.csv` | `models/*.pkl` | 2–5 min |
| 5 | `python wallet_check.py` | Wallet addresses | Risk decision | <1 sec per wallet |

## Setup and Usage

### Configure Dataset Generation

Edit `main.py` and set:

- `SEEDS_V0`, `SEEDS_V1`, `SEEDS_V2`, `SEEDS_V3`, `SEEDS_V4` — wallet seed lists
- `ENABLE_V0` through `ENABLE_V4` — enable/disable versions
- `MODE_RUN = "dual"` — recommended

### Generate Datasets

```powershell
python main.py
```

### Train Models

```powershell
python train_ml.py --model auto --token all
```

### Score Wallets

```powershell
python wallet_check.py
```

## Feature Columns

Common features across datasets:

- `wallet`
- `token`
- `wallet_age_days`
- `avg_tx`
- `recent_tx`
- `tx_frequency`
- `tx_per_min`
- `tx_per_hour`
- `tx_per_day`
- `avg_time_between_tx_sec`
- `label`

V3 adds poisoning features:

- `dust_tx_ratio`
- `similarity_hits`
- `new_sender_ratio`
- `is_poisoned_pattern`

V4 candidate datasets may also include rule-based fields such as:

- `is_high_freq`
- `is_low_value`
- `is_new_wallet`
- `risk_score_rule`

## Execution Notes

- `main.py` uses Etherscan API and page scraping. API rate limits and request timeouts are handled with retries.
- `expand_wallets()` uses a 5-minute cap per version to prevent runaway crawling.
- `wallet_check.py` prefers cached DB features but falls back to live Etherscan inference.
- `train_ml.py` uses sample weights to prioritize V1/V3/V4 examples and balance noisy auto-labeled data.

## Troubleshooting

- If `models/*.pkl` are missing, run `train_ml.py`
- If `wallet_check.py` prints `No model available`, confirm the token model files exist in `models/`
- If pool extraction is slow or missing wallets, set `USE_POOL_V*` and `MODE_RUN = "extract"` to reuse saved pools
- If Etherscan scraping fails, ensure internet access and verify scraping is not blocked by network restrictions

## Notes

- The project has both safe wallet generation (`v0`, `v4`) and malicious/poisoning detection stages (`v1`, `v2`, `v3`)
- Many dataset generation workflows in `pipeline.txt` describe older helper scripts that are no longer required when `main.py` is used directly
- Use the versioned pool files to preserve previous crawl results and prevent accidental overwrites

## Contact

Use this README as the reference for the system architecture, dataset workflow, and operational commands.

## Multi-Model Training Pipeline (XGBoost, LightGBM, RandomForest)

### Weighted Training Strategy

**Why weights?** Not all datasets are equal. V1 (manual-labeled malicious) and V3 (poisoning heuristics) are high-quality and should be emphasized. V0 is synthetic baseline, and V4 is high-confidence safe. We use **sample weights** to prioritize the most reliable labels.

**Weight assignments in `train_ml.py`:**

```python
# Smart weighting - dynamically build based on what's available
weights = []

if len(df_synth) > 0:
    weights.extend(np.ones(len(df_synth)) * 0.8)      # V0: 0.8x (synthetic)
if len(df_v1) > 0:
    weights.extend(np.ones(len(df_v1)) * 6.0)         # V1: 6.0x (HIGH PRIORITY - manual)
if len(df_v2) > 0:
    weights.extend(np.ones(len(df_v2)) * 2.5)         # V2: 2.5x
if len(df_v3) > 0:
    weights.extend(np.ones(len(df_v3)) * 4.0)         # V3: 4.0x (HIGH PRIORITY - heuristics)
if len(df_v4) > 0:
    weights.extend(np.ones(len(df_v4)) * 3.0)         # V4: 3.0x (high-confidence safe)

weights = np.array(weights)
```

**Weighting rationale:**

| Version | Weight | Reason |
|---------|--------|--------|
| **V0** | 0.8x | Synthetic baseline; less trusted than curated data |
| **V1** | 6.0x | 🔴 **HIGHEST** — manually verified malicious wallets |
| **V2** | 2.5x | Auto-labeled expansion of V1; noisier |
| **V3** | 4.0x | 🔴 **SECOND HIGHEST** — poisoning heuristics are precise |
| **V4** | 3.0x | High-confidence safe; strong signal |

**What this means:**
- V1 samples are treated as **6× more important** than V0 synthetic samples
- V3 poisoning detections are treated as **4× more important** than V0
- A single V1 malicious label is equivalent to ~7.5 V0 safe samples

**Example training with USDT (4645 rows):**

```
Loaded datasets:
  - V0: 428 rows × 0.8x = 342.4 effective samples
  - V1: 81 rows × 6.0x = 486 effective samples
  - V3: 3894 rows × 4.0x = 15,576 effective samples
  - V4: 242 rows × 3.0x = 726 effective samples
  ────────────────────────────────────────────
  Total effective samples: 17,130+ (vs 4,645 raw)

Label distribution (raw):
  - -1 (unknown): 3798 rows
  - 0 (safe): 670 rows
  - 1 (malicious): 81 rows
  - 2 (poisoned): 96 rows
```

**How weights are applied:**

In `train_ml.py`, the model's `.fit()` call includes weights:

```python
# For RandomForest
m.fit(X_train, y_train, sample_weight=w_train)

# For XGBoost / LightGBM
m.fit(X_train, y_train, sample_weight=w_train, eval_set=[(X_val, y_val)], 
      early_stopping_rounds=20, verbose=False)
```

The model optimizer **emphasizes errors on high-weight samples**, so:
- Misclassifying V1 malicious samples costs ~6× more (penalizes mistakes on manually-verified data)
- Misclassifying V3 poisoned samples costs ~4× more (penalizes mistakes on heuristic detections)
- Misclassifying V0 synthetic samples costs ~0.8× less (tolerates some error on synthetic data)

**Result:** The model learns to be extremely conservative with high-quality labels and more tolerant of noisier data.

### Architecture Overview

The system uses three machine learning models, all implemented in **`train_ml.py`**:

1. **RandomForest** (baseline, always available)
   - Implementation: scikit-learn's `RandomForestClassifier`
   - Location in `train_ml.py`: lines ~260–275 (model instantiation)
   - Default: n_estimators=150, max_depth=14, class_weight="balanced"
   - Used when: always compiled; fallback if boosters unavailable

2. **XGBoost** (optional booster)
   - Implementation: `from xgboost import XGBClassifier`
   - Location in `train_ml.py`: lines ~277–283 (model instantiation)
   - Default: n_estimators=200, max_depth=6, eval_metric='mlogloss', early_stopping_rounds=20
   - Used when: `pip install xgboost` is completed; skipped with warning if unavailable

3. **LightGBM** (optional booster)
   - Implementation: `from lightgbm import LGBMClassifier`
   - Location in `train_ml.py`: lines ~286–292 (model instantiation)
   - Default: n_estimators=200, early_stopping_rounds=20
   - Used when: `pip install lightgbm` is completed; skipped with warning if unavailable

### How the Models Are Applied

**In `train_ml.py`:**

- `train_token_model(token, model_choice="auto")` function (lines ~115–300):
  1. Loads CSV datasets for versions V0, V1, V2, V3, V4 from `datasets/`
  2. Combines all rows and applies sample weights (V1/V3 weighted higher for quality)
  3. Scales features using `StandardScaler`
  4. Splits into train/validation sets (80/20, stratified when possible)
  5. Instantiates all available models (RF always; XGB/LGB if installed)
  6. **Trains each model** in a loop (lines ~295–313):
     - RF uses `model.fit(X_train, y_train, sample_weight=w_train)`
     - XGB/LGB use early stopping with validation set: `model.fit(..., eval_set=[(X_val, y_val)], early_stopping_rounds=20, ...)`
  7. **Evaluates each model** on validation set using macro F1 score
  8. **Selects best model** by highest F1
  9. **Saves best model** to:
     - `models/{token}_model.pkl` (primary artifact)
     - `models/{token}_model_{rf|xgb|lgb}.pkl` (named copy)
     - `models/{token}_scaler.pkl`
     - `models/{token}_features.pkl`

### End-to-End Pipeline: `main.py` → `train_ml.py`

When you run the system as intended:

```powershell
# Step 1: Generate datasets (main.py in dual mode)
python main.py --mode dual

# Step 2: Train models with auto-selected best estimator (train_ml.py)
python train_ml.py --model auto --token all
```

**Step 1** (`main.py --mode dual`):
- Expands wallet pools from seeds (V0–V4)
- Extracts per-token features
- **Outputs "ready" CSVs** to `datasets/`:
  - `v0_<token>.csv` (baseline safe wallets)
  - `v1_<token>.csv` (malicious wallets)
  - `v3_<token>.csv` (poisoned wallets)
  - `v4_<token>.csv` (high-confidence safe)
  - `<token>_training_ready.csv` (V0 aggregated for training seed)

**Step 2** (`train_ml.py --model auto --token all`):
- Reads all `v*_<token>.csv` files from `datasets/`
- Combines rows with weighted sample importance
- Trains RF, XGB, LGB in parallel
- Compares validation F1 scores
- **Selects best model** (e.g., RF with F1=0.83)
- **Saves to `models/`**

### CLI Usage Examples

```powershell
# Auto-select best model for all tokens (recommended)
python train_ml.py --model auto --token all

# Train only RandomForest for USDT
python train_ml.py --model rf --token usdt

# Train only XGBoost for USDC
python train_ml.py --model xgb --token usdc

# Train only LightGBM for DAI
python train_ml.py --model lgb --token dai

# Train auto (RF/XGB/LGB) for one token
python train_ml.py --model auto --token busd
```

### Installing Optional Boosters

To use XGBoost and LightGBM (optional):

```powershell
pip install xgboost lightgbm
```

If not installed, `train_ml.py` continues with RandomForest as fallback.

## Rule-Based Heuristics (Defensive Filtering)

**Why?** The dataset has severe class imbalance (safe:risk ≈ 4.9:1), and 73.8% of samples are "unknown" (-1). Rule-based heuristics ensure high-risk wallets are caught even if ML confidence is low.

**Implemented in `wallet_check.py`:**

The `apply_rule_based_filters()` function fires BEFORE ML classification to catch known attack patterns:

```python
def apply_rule_based_filters(features, prob_malicious, prob_poisoned):
    """Apply deterministic checks to catch high-risk patterns."""
    
    # Rule 1: NEW WALLET (< 7 days) with ANY suspicious activity
    if features['wallet_age_days'] <= 7:
        if prob_malicious > 0.3 or prob_poisoned > 0.2:
            return "REVIEW", "new_wallet_suspicious"
    
    # Rule 2: SPAM PATTERN (ultra-high frequency + low value)
    if features['tx_per_day'] > 50 and features['avg_tx'] < 1.0:
        return "BLOCK", "spam_pattern_high_freq_low_value"
    
    # Rule 3: NO MEANINGFUL ACTIVITY (dust-only transactions)
    if features['avg_tx'] < 0.001 and features['tx_frequency'] > 10:
        return "BLOCK", "no_meaningful_activity"
    
    # Rule 4: BOT ACTIVITY (instant transactions: <10 sec apart)
    if features['avg_time_between_tx_sec'] < 10 and features['tx_frequency'] > 5:
        return "BLOCK", "bot_activity_instant_txs"
    
    # Rule 5: UNUSUAL SPIKE (dormant wallet + recent spike)
    if (features['recent_tx'] > features['avg_tx'] * 10 and
        features['wallet_age_days'] > 365):
        return "REVIEW", "unusual_spike_old_wallet"
    
    # Rule 6: ABNORMAL HOURLY RATE (> 20 txs/hour)
    if features['tx_per_hour'] > 20:
        return "REVIEW", "abnormal_tx_rate_hourly"
    
    return None  # No rule fired; continue with ML
```

**Rules prioritize:**
1. **Poisoning attacks** (address spoofing, dust spam, high-frequency attacks)
2. **New wallet risks** (< 7 days old with suspicious patterns)
3. **Bot activity** (instant transactions)
4. **Anomalous behavior** (activity spikes on dormant accounts)

**Output:** If a rule fires, the wallet is classified immediately (no ML needed). Examples:
- Wallet with 100 txs/day of $0.001 each → `BLOCK` (spam_pattern)
- 6-day-old wallet with 2000 txs → `REVIEW` (new_wallet_suspicious)
- Old wallet suddenly 50 txs/hour → `REVIEW` (unusual_spike)

## Class Imbalance Handling (Training)

**Problem:** Training data has 4.9:1 safe-to-risk ratio, with 73.8% unknown labels.

**Solution:** In `train_ml.py`, we **oversample minority classes** during training:

```python
# Separate labeled vs unknown samples
labeled = y[y != -1]           # Keep 0, 1, 2 labels
unknown = y[y == -1]           # Set aside -1 (unknown)

# Oversample malicious/poisoned (1, 2) to balance
safe_count = len(labeled[labeled == 0])
risk_count = len(labeled[labeled.isin([1, 2])])

# If risk:safe < 1:3, duplicate risk samples
if risk_count < safe_count // 3:
    target = safe_count // 3
    risk_samples_boosted = resample(risk_samples, n_samples=target)
    # Now risk:safe ≈ 1:3 balanced
```

**Effect:**
- Malicious/poisoned examples get more training emphasis
- Model learns attack patterns better
- Reduces false negatives (missed attacks)

---

## Decision Flow: Rules + ML

When `wallet_check.py` scores a wallet:

```
1. Fetch features
   ↓
2. Apply RULE-BASED HEURISTICS
   ├─ If rule fires → return BLOCK/REVIEW immediately
   └─ If no rule → continue to ML
   ↓
3. Load best ML model (RF/XGB/LGB)
   ↓
4. Get probabilities: (normal, malicious, poisoned)
   ↓
5. Apply ML thresholds
   ├─ poisoned >= 0.5  → BLOCK
   ├─ malicious >= 0.8 → BLOCK
   ├─ malicious >= 0.5 → REVIEW
   └─ else            → ALLOW
```

### Files Involved

| File | Role |
|------|------|
| `main.py` | Generates v0–v4 CSVs and "ready" training datasets |
| `train_ml.py` | Loads CSVs, trains RF/XGB/LGB, saves best model |
| `wallet_check.py` | Loads `models/{token}_model.pkl` and scores wallets |
| `requirements.txt` | Lists optional booster dependencies |

## Files Involved

| File | Role |
|------|------|
| `main.py` | Generates v0–v4 CSVs and "ready" training datasets |
| `train_ml.py` | Loads CSVs, oversamples minorities, trains RF/XGB/LGB, saves best model |
| `wallet_check.py` | Applies rule-based heuristics + loads model for scoring |
| `requirements.txt` | Lists optional booster dependencies |

## Recent Changes (added multi-model training)

- Implemented multi-model training in `train_ml.py`: RandomForest (baseline), XGBoost (`xgboost`), and LightGBM (`lightgbm`). 
- Multi-model support ensures robust model selection and automatic fallback to RF if boosters are unavailable.
- Files changed:
  - `train_ml.py` — added multi-model training & model selection logic
  - `main.py` — V3 poisoning heuristics and zero-value filtering (preserve tiny dust amounts)
  - `wallet_check.py` — runtime feature generation updated to skip zero-value transfers
  - `README.md` — comprehensive model documentation
  - `requirements.txt` — new file listing optional booster dependencies
