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
