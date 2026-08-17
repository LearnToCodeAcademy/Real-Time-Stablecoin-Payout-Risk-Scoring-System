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

## 2026-08-17 - Phases 2-4 Build, Bugs, And Collection

Changed:

- Split and pinned core, API, ML, dashboard, deep, and development dependencies.
- Added LF normalization, Docker API image, PostgreSQL/Redis Compose stack, and
  import-safe optional deep/GNN boundaries.
- Added the `risk_system` package with canonical contracts/features, a rotating
  rate-limited Etherscan V2 client, and a resumable 1-1,000,000 wallet collector.
- Fixed malformed seed-list entries and preserved the three-level runtime token
  detection fallback.
- Moved historical root documentation into `docs/history/` without deleting it.
- Added CLI collection with a 50,000-wallet default and browser controls for
  target, tokens, seeds, progress, cancellation, and checkpoint recovery.

Verified:

- Collector regression test passes with a deterministic fake Etherscan client.
- Real data outputs are always label `-1` until a trusted label is supplied.
- Etherscan V2 endpoint and rate-limit behavior were checked against official
  documentation before implementing calls/backoff.

Not verified / limitations:

- A complete 50,000-wallet live crawl was not launched because the current
  untracked `.env` has no Etherscan key and such a crawl is intentionally long.
- Internal-transaction, contract-age, and network-gas features remain planned;
  activating them without a historical backfill would break schema parity.

## 2026-08-17 - Phase 5 Honest Training And Versioning

Changed:

- Added wallet identity deduplication/conflict removal, stratified 70/15/15
  splits, fold-local scaling, untouched tests, candidate CV, class weighting,
  0-200 Optuna TPE trials, immutable model versions, atomic activation, reports,
  cancellation, and rollback.
- Added script and browser workflows for train, evaluate, history, and restore.

Verified:

- Ran 50 Optuna trials plus RF/XGBoost/LightGBM comparison for USDT and USDC.
- USDT active version `20260817T103942Z-a5507b2608ba-usdt`: test accuracy
  0.9517, macro F1 0.8531, malicious recall 0.4167, poisoned recall 1.0000.
- USDC active version `20260817T104145Z-13acbb927b75-usdc`: test accuracy
  0.9394, macro F1 0.8673, malicious recall 0.6364, poisoned recall 1.0000.
- Machine-generated reports include split distributions, per-class metrics,
  confusion matrices, ROC-AUC, CV mean/std, and NOT MET safety status.

Limitations:

- Neither model meets the 0.90 macro-F1 plus 0.90 malicious/poisoned recall
  target. More independently verified malicious labels are required.
- Other tokens are skipped when a class is missing or the smallest class has
  fewer than ten trusted wallets.

## 2026-08-17 - Phases 6-8 API, Console, And Real Streaming

Changed:

- Productionized FastAPI with SHA-256 API-key checks, configurable CORS/rate
  limiting, Redis/memory score cache, PostgreSQL health integration, JSON logs,
  Prometheus metrics, typed request validation, job persistence, and dependency
  health probes.
- Replaced sample live alerts with provider WebSocket/Etherscan Transfer logs,
  reconnect backoff, bounded scoring, SQLite events/cases, and one WebSocket
  bridge used by both API and standalone listener.
- Added the React/TypeScript command center, investigate, live stream, graph,
  case management, model analytics, training/collection, and settings views.
- Kept Streamlit as a legacy/internal tool; React is the maintained primary UI.

Verified:

- API integration tests confirm health and WebSocket status behavior and assert
  that no demo event is emitted when a real provider is absent.
- Live parser/store tests confirm real log identity and shared case creation.
- Frontend unit, lint, strict TypeScript build, and production Vite build pass.

## 2026-08-17 - Phases 9-10 Quality And Documentation

Changed:

- Added organized pytest tests, Ruff, mypy, Vitest, ESLint, GitHub Actions,
  detect-secrets pre-commit/CI scanning, Docker files, and generated reports.
- Rewrote README.md, technical.txt, frontend/README.md, ARCHITECTURE.md,
  FEATURES.md, and DEEP_MODELS.md; archived the full original build request.
- Added one-command local startup and separate checker/training localhost URLs.
- Credited John Marwin Ebona in the README and technical reference.

Outstanding highest-priority manual security action:

- Rotate every previously exposed Etherscan/database credential. Current HEAD
  is environment-only, but the old Git history remains sensitive.
- A combined `git filter-repo` history rewrite for leaked secrets and old binary
  artifacts requires a coordinated destructive force-push and all collaborators
  must re-clone. It is not claimed complete in this log.

## 2026-08-17 - Reputation-First, Fail-Closed Scoring

Changed:

- Added provider-backed reputation screening before transaction features or ML,
  with attributed local CSV feeds, Etherscan Metadata, Chainabuse, and optional
  explicit public Etherscan warning checks.
- Added a Gas Guzzlers synchronizer that imports only rows carrying an explicit
  phishing/scam label; high gas usage by itself is never a malicious label.
- Changed missing provider/history behavior to REVIEW / UNSCORABLE with null
  probabilities, so unknown evidence cannot render as Normal 0%.
- Added threat-intelligence UI attribution, collection label provenance, API
  sync control, tests, and operator documentation.

Verified:

- All three user-supplied Etherscan-labeled samples dynamically returned BLOCK
  from current provider data without embedding their addresses in source code.
- A clean synthetic address with a risky counterparty in its transaction table
  remained unscorable rather than becoming a false-positive reputation match.
- Source audit found no supplied wallet literals after legacy seed cleanup.
