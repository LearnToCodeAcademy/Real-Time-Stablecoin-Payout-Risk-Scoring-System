# Implementation Log

## 2026-08-17 - Phase 0 Audit

Changed:

- Added `AUDIT.md` with verified findings from the current repository.

Verified:

- Hardcoded Etherscan keys exist in `main.py` and `wallet_check.py`.
- `.env` is tracked despite `.gitignore`.
- Git history contains `.env`.
- Git history contains hardcoded API-key patterns.
- `train_ml.py` scales and resamples before validation splitting.
- `gnn_model.py` fails on import without PyTorch.
- `api.py`, `dashboard.py`, and `graph_engine.py` fail imports in the bundled
  Python environment due to missing dependencies.
- `stream_listener.py` imports but reports missing websocket dependencies.
- `db.py` contains CRCR line-ending artifacts.
- No `.github/workflows/`, `Dockerfile`, `pyproject.toml`, or `pytest.ini`
  exists.
- Eight root-level `test_*.py` files exist but are not organized/configured.

Not verified:

- A clean virtualenv install of `requirements.txt` was not completed during
  this pass.
- Full Git history secret scrubbing was not performed because it requires a
  coordinated destructive history rewrite and force-push.
- Etherscan live documentation was not consulted during this audit because no
  endpoint behavior was changed.

Risks/TODO:

- Rotate exposed Etherscan and database credentials immediately.
- Remove `.env` from tracking.
- Move hardcoded API keys to environment variables.
- Add CI and secret scanning before further production work.
- Refactor ML training to avoid validation leakage before publishing metrics.

## 2026-08-17 - Phase 1 Security And Runtime Fixes

Changed:

- Replaced active hardcoded Etherscan API key configuration in `main.py` and
  `wallet_check.py` with environment-variable loading.
- Added `.env.example` with placeholders.
- Removed `.env` from Git tracking while leaving the local file on disk.
- Expanded `requirements.txt` for API, dashboard, graph, and stream runtime
  dependencies.
- Made `gnn_model.py` import-safe when PyTorch/PyTorch Geometric are absent.
- Normalized `db.py` line endings.
- Updated `stream_listener.py` to read provider URLs from `ALCHEMY_WS_URL` or
  `INFURA_WS_URL`.
- Refactored `train_ml.py` so validation splitting happens before scaler fitting
  and oversampling.
- Added local-only training API endpoints with model snapshot rollback.
- Added `checker.html` and `training.html` static UI surfaces.
- Added a guarded `/ws/live-alerts` websocket endpoint for the checker UI.

Verified:

- Installed `requirements.txt` into a local `.venv`.
- `api.py`, `dashboard.py`, `gnn_model.py`, `graph_engine.py`, and
  `stream_listener.py` import successfully in the local `.venv` when DB is
  disabled for the check.
- `api.py`, `dashboard.py`, `gnn_model.py`, `stream_listener.py`,
  `train_ml.py`, `wallet_check.py`, `main.py`, and `db.py` pass Python
  compilation.
- `GET /health`, `GET /model_info`, and `GET /training/history` return HTTP
  200 from the local FastAPI server.
- `checker.html` and `training.html` return HTTP 200 from the local static
  server.
- Browser check confirmed `checker.html` loads, `/ws/live-alerts` reports
  online, feed rows appear, and `training.html` loads.
- Secret pattern re-check on edited docs/code found no previously exposed
  Etherscan key strings.

Not verified:

- Real Etherscan-backed retraining was not run because this pass should not use
  or expose private credentials.
- Git history scrubbing was not performed because it requires a coordinated
  history rewrite and force-push.
- `/ws/live-alerts` currently emits local sample events; it is not yet bridged
  to real provider stream data.

Risks/TODO:

- Rotate credentials and scrub Git history.
- Add API auth/rate limiting before exposing the API publicly.
- Replace the sample websocket stream with a real stream_listener.py bridge.
- Generate fresh model performance reports by running the corrected training
  pipeline on current datasets.
