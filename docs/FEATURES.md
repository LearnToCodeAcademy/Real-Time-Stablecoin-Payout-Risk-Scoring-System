# Canonical Feature Reference

The active trainer and collector share `risk_system.features.FEATURE_COLUMNS`. A model version stores its exact ordered feature list next to the model and scaler, and runtime inference aligns by that stored order.

| Feature | Computation | Risk rationale |
|---|---|---|
| `wallet_age_days` | Days between earliest and latest sampled transfers, minimum one. | Short histories are less established. |
| `avg_tx` | `log1p` mean token value. | Stabilizes broad value ranges. |
| `recent_tx` | `log1p` latest token value. | Captures abrupt recent behavior. |
| `tx_frequency` | Transfers divided by wallet-age days. | General activity density. |
| `tx_per_min` | Transfers over observed minutes. | High-frequency automation signal. |
| `tx_per_hour` | Transfers over observed hours. | Bot/spam cadence signal. |
| `tx_per_day` | Transfers over observed days. | Longer-window intensity. |
| `avg_time_between_tx_sec` | Mean adjacent transfer interval. | Machine-like timing can differ from normal use. |
| `dust_tx_ratio` | Fraction below 0.001 token. | Address-poisoning and spam indicator. |
| `similarity_hits` | Senders sharing wallet prefix and suffix. | Direct poisoning-pattern feature. |
| `new_sender_ratio` | Unique senders divided by transfers. | Measures counterparty churn. |
| `is_poisoned_pattern` | Dust majority plus similarity and sender churn. | Explicit high-signal heuristic. |
| `tiny_tx_count` | Count below 0.01 token. | Repeated tiny transfers indicate spam/probing. |
| `unique_receivers` | Unique destination addresses. | Distribution/dispersion behavior. |
| `avg_tx_value` | `log1p` mean value, retained for historical schema compatibility. | Value magnitude. |
| `window_days` | Observation window in days. | Normalizes duration-dependent signals. |
| `repeat_small_to_count` | Repeated small destinations. | Repetitive dust routing. |
| `no_meaningful_flow` | One when maximum value stays below 0.01. | Wallet may contain only dust artifacts. |
| `short_time_window` | One when all sampled transfers fit inside 24 hours. | Burst/new-wallet signal. |

## Source Contract

Collection uses the Etherscan V2 `account/tokentx` result. Live monitoring uses ERC-20 `Transfer` logs from Ethereum JSON-RPC subscriptions or Etherscan's logs endpoint. New feature work must update the canonical list, collector, runtime generator, tests, and versioned artifact schema together.

Internal transactions, contract verification/creation age, and network-relative gas anomalies are intentionally not claimed as active model inputs yet. The Etherscan client can be extended for them, but they require additional request budgets and a complete labeled-data backfill before deployment; adding columns only at inference time would create schema drift.
