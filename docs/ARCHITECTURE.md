# Architecture

## Runtime Boundaries

The React console is presentation only. It calls FastAPI for every score, case mutation, model operation, collection job, and graph query. FastAPI owns authentication, throttling, cache policy, persistence, provider connectivity, and ML invocation.

`LiveEventBroker` chooses one real source at startup: an Ethereum JSON-RPC WebSocket from `ALCHEMY_WS_URL`, `INFURA_WS_URL`, or `ETH_RPC_WS_URL`; otherwise Etherscan V2 polling when a key is present. Without either source it reports offline. Parsed ERC-20 transfer logs contain a transaction hash, log index, block number, parties, token, amount, source, and `verified_real=true` before entering the shared event store.

## Data And Model Flow

1. `ReputationService` checks attributed local feeds and enabled remote providers before behavioral scoring. A match blocks; provider absence does not imply safety.
2. `WalletCollector` starts from operator seeds or local pools and performs resumable breadth-first expansion through documented token-transfer records.
3. Each job writes `wallets.csv`, `features.csv`, `processed.txt`, and an atomic `checkpoint.json` under `data/collections/<job-id>/`.
4. Unknown discoveries remain label `-1`. Attributed risk-feed entries may enter as label `1`; `ModelTrainer` accepts only labels `0`, `1`, and `2`, removes conflicting wallet identities, and keeps one row per wallet.
5. Data is split by unique wallet into train, validation, and untouched test sets. Scaling and class weighting occur inside the training boundary.
6. Candidate models are compared with stratified cross-validation and validation metrics. Optional Optuna TPE trials tune LightGBM against macro F1 plus a fraud-recall floor.
7. The selected model is refit on train+validation and evaluated once on test. Artifacts and metrics are stored under `model_versions/<version>/`, copied atomically into `models/`, and referenced by `model_versions/active.json`.
8. `wallet_check.py` loads the active token artifact lazily. Runtime rules can force REVIEW/BLOCK; otherwise the trained classifier returns class probabilities used by token-aware decision thresholds.

## Persistence

| Store | Responsibility |
|---|---|
| PostgreSQL | Durable wallet feature and label cache through `db.py`. |
| Redis | Fast feature lookups and short-lived API score-response caching. |
| SQLite | Local real-event, alert, case, assignment, note, and state persistence. |
| Filesystem | Collection checkpoints, training jobs, immutable model versions, active artifacts, and generated reports. |

SQLite keeps standalone setup immediate. PostgreSQL and Redis are optional locally and are provisioned by Compose for a production-like stack.

## API Surface

The service exposes health/model metadata, single and batch scoring, alert statistics, cases, graph data, collection jobs, training jobs, version listing/rollback, a Prometheus endpoint, and `/ws/live-alerts`. Mutating training and collection routes require localhost mode plus `ENABLE_LOCAL_TRAINING=true`; static hosting cannot unlock them.

## Failure Behavior

- Missing chain credentials: live state is offline and the feed stays empty.
- Threat-intelligence match: scoring stops early with BLOCK and provider attribution.
- Missing transaction evidence/provider failure: REVIEW / UNSCORABLE with null probabilities, never a fabricated zero-risk result.
- Provider disconnect: WebSocket reconnection uses exponential backoff up to 30 seconds.
- Etherscan throttle: key rotation, per-key pacing, Retry-After support, exponential backoff, and jitter.
- Missing model: scoring returns REVIEW with an explicit model-unavailable reason.
- Missing label class: training fails or skips that token with class counts.
- Redis/Postgres outage: health reports degradation; local memory/SQLite behavior remains available where applicable.

## Deployment Shapes

- Local: `scripts/start_local.py` launches API and Vite with training enabled.
- Containers: Compose launches API, PostgreSQL, and Redis; model/data directories are mounted.
- Netlify: builds `frontend/dist` only. It is a read-only console and needs a separately deployed API for live data.
- Stream-only worker: `stream_listener.py` prints real normalized events for pipeline integration without the browser.
