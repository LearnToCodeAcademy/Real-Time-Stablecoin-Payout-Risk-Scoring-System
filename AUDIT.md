# Audit Report

Date: 2026-08-17

Credit: John Marwin Ebona

This audit was created after re-reading the full pasted build prompt and
checking the current repository state. Sensitive values are intentionally not
printed here.

## Executive Summary

The repository has a working Python-oriented system shape, but it is not yet in
a production-safe state. The most urgent issues are hardcoded API keys, a
tracked `.env`, incomplete dependencies, an import-breaking optional GNN module,
ML methodology leakage in `train_ml.py`, tracked generated artifacts, and no CI
or test runner configuration.

## Verified Findings

### P0: Secrets In Source

- `main.py` contains a hardcoded default Etherscan key and a `VERSION_API_KEYS`
  dictionary with hardcoded values.
- `wallet_check.py` contains a separate hardcoded Etherscan key.
- `.env` is tracked by Git even though `.gitignore` excludes `.env`.
- `.env` contains a real-looking `DATABASE_URL`.
- Git history contains `.env`.
- Git history contains commits matching hardcoded API-key patterns in
  `main.py` and `wallet_check.py`.
- A current-tree secret pattern scan found 3 files with likely sensitive
  patterns.

Action required:

- Move all keys to environment variables.
- Remove `.env` from Git tracking.
- Add `.env.example` with placeholders.
- Rotate exposed keys and database credentials.
- Scrub secrets from Git history with `git filter-repo` or BFG, then force-push
  only after coordinating with collaborators.

### P0: ML Validation Leakage

`train_ml.py` currently performs preprocessing before validation splitting:

- `StandardScaler.fit_transform(X)` appears before `train_test_split`.
- `resample(...)` is used before `train_test_split`.

This can leak validation-set statistics and duplicated rows into validation.
Existing accuracy/F1 claims should be treated as untrusted until a leakage-free
train/validation/test pipeline is implemented.

### P1: Optional GNN Module Fails Import Without PyTorch

`gnn_model.py` conditionally imports PyTorch, but classes inherit from
`nn.Module` at module scope. In an environment without PyTorch, importing
`gnn_model.py` fails with:

- `NameError: name 'nn' is not defined`

This confirms the graceful-degradation path is currently broken.

### P1: Dependency File Is Incomplete

Current `requirements.txt` includes:

- pandas
- numpy
- requests
- beautifulsoup4
- scikit-learn
- psycopg2-binary
- python-dotenv
- xgboost
- lightgbm

Import checks in the bundled Python environment found:

- `api`: fails because `fastapi` is missing.
- `dashboard`: fails because `streamlit` is missing.
- `gnn_model`: fails because PyTorch is missing and fallback is broken.
- `deep_model`: imports, but logs missing TensorFlow/PyTorch warnings.
- `graph_engine`: fails because `networkx` is missing.
- `stream_listener`: imports, but logs missing `websockets` and `aiohttp`.

Action required:

- Add runtime/API/dashboard/stream dependencies.
- Treat heavy deep-learning libraries as optional extras unless the project is
  ready to support them.

### P1: `db.py` Has Mixed/Corrupted Line Endings

Raw byte inspection found 168 CRCR sequences in `db.py`. This should be
normalized to stable line endings before substantial edits.

### P1: Generated Data And Models Are Tracked

The repository tracks generated CSV and pickle artifacts despite `.gitignore`
excluding those file types.

Observed:

- 71 tracked files match `.env`, `.csv`, or `.pkl`.
- `backup models/` contains tracked pickle model artifacts.
- `datasets deprecated/` contains tracked CSV datasets.

Action required:

- Decide which artifacts are intentionally versioned.
- Move large generated data/model artifacts to releases, object storage, or a
  documented artifact path.
- Keep source control focused on source, configs, docs, and small fixtures.

### P2: Missing Project Automation

No project automation was found:

- No `.github/workflows/` directory.
- No `Dockerfile`.
- No `pyproject.toml`.
- No `pytest.ini`.

Eight root-level test files exist but are not organized under `tests/`:

- `test_contract_skip.py`
- `test_decision_fix.py`
- `test_feature_fix.py`
- `test_rules.py`
- `test_token_detect.py`
- `test_token_expansion.py`
- `test_token_integration.py`
- `test_wallet_check_fix.py`

### P2: Loose Historical Documentation

The repository contains several root-level historical docs:

- `CRITICAL_FIX_SUMMARY.md`: token detection flaw summary and fix notes.
- `TOKEN_DETECTION_FIX.md`: deeper token detection root-cause analysis.
- `WALLET_CHECK_USAGE_GUIDE.md`: `wallet_check.py` usage and troubleshooting.
- `TOKEN_EXPANSION_README.md`: token support expansion summary.
- `TOKEN_SPECIFIC_RULES.md`: token-specific scoring/training rules.
- `MULTI_TOKEN_IMPLEMENTATION.md`: multi-token implementation details.
- `MULTI_TOKEN_SETUP_COMPLETE.md`: multi-token completion report.

These files preserve useful history but should eventually be consolidated into a
`docs/` folder with one canonical architecture guide and one usage guide.

## Current Localhost State

The static overview added in the previous commit is reachable at:

- `http://localhost:8080/`

The full API server was not verified in this audit because the current
environment lacks required API dependencies from `requirements.txt`.

## Work Not Yet Completed

The full pasted prompt also asks for:

- API production hardening.
- Secret scanning and CI.
- WebSocket live alert bridging.
- A production React/Vite security console.
- Local-only training UI with version history, accuracy tracking, and rollback.
- Leakage-free retraining and generated model performance reports.
- Full documentation consolidation.

Those are not completed by this audit. They should proceed after P0 security
cleanup.
