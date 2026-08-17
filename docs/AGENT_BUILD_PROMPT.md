
first of all pull this:
https://github.com/qjmre23/Real-Time-Stablecoin-Payout-Risk-Scoring-System

do all below and make sure to train more using my Api's from etherscan, or create a web gui where when i click train it will train, directly parse those result in the ML, rules, everything, and each time i train there is accuracy level so i can see what version is accurate and reverse button so i can reverse to the previous train reverting all changes, make sure this is a massive upgrade, tech level, and out of this world system
the words below are just,, some. you can and free to add more if you found any errors, problem and add more features dont mind the api etherscans its fine since they are free and public anyway


also if possible i want this to be cross platform meaning when i attached this repo to netlify the web checking will work, it also work as standalone,  training is not allowed in web host (netlify) but only in standalone or local using (traning.html) make sure the web checker looks sick, has an impressive looking UI, the ui must look like https://www.blockchain.com/explorer	, it has graphs, live feed of new (real, updates every second) of infected wallets, top wallets that are infected, and many more all is functional, responsive and top grade UI.
 🔐 Real-Time Stablecoin & Token Payout Risk Scoring System

> Pre-transaction wallet risk intelligence for stablecoin and token payments — behavioral analytics + ML + rule-based heuristics + graph intelligence, combined into a real-time ALLOW / REVIEW / BLOCK decision engine.

---

## 📌 What This Document Is

This README contains two things:

1. **A short, accurate description of the system as it actually exists today** (not aspirational — verified against the real code, not just old docs).
2. **A single, massive, self-contained build prompt** (below, in the fenced block) intended to be pasted directly into an autonomous coding agent (OpenAI Codex / Codex CLI, Claude Code, GPT-5.1-Codex, Cursor Agent, etc.) to drive a multi-session engineering effort that:
   - Fixes every verified bug, security hole, and methodology flaw described here
   - Expands the Etherscan-sourced training data properly
   - Rebuilds the ML pipeline to produce **honest, reproducible, verifiable ≥90% performance** (defined precisely — accuracy alone is a misleading target on this dataset; see the prompt)
   - Ships a genuinely production-grade, real-time "blockchain security admin console" web UI
   - Leaves the repo in a state a security-conscious reviewer would actually approve

The prompt is written to be pasted **as-is** into the agent. It's long on purpose — every ambiguous instruction is a place an agent will improvise or hallucinate a wrong answer, so this spells out file names, current line numbers, current behavior, desired behavior, and explicit "do not guess, verify instead" instructions throughout.

---

## 🧭 Actual Current Architecture (verified against source, not assumed)

```
Etherscan API (v2 unified endpoint)
        │
        ▼
main.py — wallet graph expansion + V0–V4 dataset generation (54 tokens)
        │
        ▼
datasets/*.csv  ──────────────►  train_ml.py — RF / XGBoost / LightGBM training
        │                                 │
        ▼                                 ▼
db.py (Postgres feature/label cache)   models/*.pkl (per-token model + scaler + feature list)
        │                                 │
        └──────────────┬──────────────────┘
                        ▼
              wallet_check.py — rule engine + ML inference + decision logic
                        │
        ┌───────────────┼────────────────────┐
        ▼               ▼                    ▼
   api.py          dashboard.py        stream_listener.py
 (FastAPI REST   (Streamlit           (WebSocket listener for
  scoring API,    visualization        live Alchemy/Infura feeds,
  already exists  dashboard,           buffered batch scoring,
  but undocumented) already exists    alerting — already exists
                   but undocumented)   but undocumented)

Also present, currently broken on a clean install:
graph_engine.py — NetworkX-based wallet clustering / graph features
gnn_model.py     — PyTorch-Geometric GCN/GAT/GraphSAGE fraud models
                   (crashes on import without torch — see Phase 2)
deep_model.py    — TensorFlow LSTM / Transformer sequence models (optional-safe)
```

**Important correction vs. the old README text:** the previous README described the API layer as "Go (planned)" and the client as a "Browser Extension." Neither of those exist in the repo. What *does* exist and already works (modulo the bugs below) is a Python FastAPI service (`api.py`) and a Streamlit dashboard (`dashboard.py`). The rebuilt README this prompt produces should describe reality, not aspiration.

### Verified, currently-broken or currently-risky pieces

- `gnn_model.py` — `class GCNFraudDetector(nn.Module):` (and `GATFraudDetector`, `GraphSAGEFraudDetector`) are defined at module scope, unconditionally inheriting from `torch.nn.Module`. `torch` is only imported inside a `try/except ImportError` guard, and `torch` is not in `requirements.txt`. **Any import of `gnn_model.py` on a machine without PyTorch installed raises `NameError: name 'nn' is not defined` immediately**, not a graceful degradation as the surrounding code comments imply.
- `train_ml.py` — `resample()`-based oversampling of the malicious/poisoned classes happens *before* `train_test_split`, and `StandardScaler.fit_transform` is called on the full combined dataset before the split. This is textbook train/validation leakage: duplicated rows from oversampling can appear in both the training fold and the validation fold, and the scaler "sees" validation data statistics during fit. Reported F1/accuracy numbers from the current pipeline should not be trusted as generalization estimates.
- `requirements.txt` lists 9 packages (`pandas`, `numpy`, `requests`, `beautifulsoup4`, `scikit-learn`, `psycopg2-binary`, `python-dotenv`, `xgboost`, `lightgbm`). It does not list `fastapi`, `uvicorn`, `pydantic` (needed by `api.py`), `streamlit`, `plotly`, `networkx` (needed by `dashboard.py`/`graph_engine.py`), or `websockets`/`aiohttp` (needed by `stream_listener.py`). A clean `pip install -r requirements.txt` does not give you a working system.
- `db.py` has corrupted/mixed line endings (literal `\r\r` sequences visible in the raw file), suggesting repeated Windows/Unix round-tripping without normalization.
- `backup models/` (27MB of `.pkl` files) and `datasets deprecated/` (4MB, 57 CSV files) are committed to git despite `.gitignore` explicitly excluding `*.pkl` and `*.csv` — meaning they were force-added (`git add -f`) at some point and are now permanently bloating the repository history.
- Seven loose, overlapping status/fix-summary markdown files sit at repo root (`CRITICAL_FIX_SUMMARY.md`, `MULTI_TOKEN_IMPLEMENTATION.md`, `MULTI_TOKEN_SETUP_COMPLETE.md`, `TOKEN_DETECTION_FIX.md`, `TOKEN_EXPANSION_README.md`, `TOKEN_SPECIFIC_RULES.md`, `WALLET_CHECK_USAGE_GUIDE.md`), plus stray `pipeline.txt`, `structure.txt`, `structure copy.txt` — no `docs/` folder, no single source of truth.
- No CI workflow, no `Dockerfile`, no `pytest.ini`/`pyproject.toml`. The eight `test_*.py` files at the repo root exist but nothing runs them automatically.

None of the above is guesswork — it was confirmed by pulling the actual repository contents and reading the referenced files and line ranges directly.

---

## 🤖 MASTER BUILD PROMPT — paste everything in the fenced block below into your coding agent

Copy the entire contents of the code block that follows (from `You are an autonomous senior engineering agent` to the final `END OF PROMPT` line) into Codex / Claude Code / your agent of choice as a single task. It is intentionally long, explicit, and repetitive in places — that repetition is deliberate, to keep a long-running agent anchored to the actual repo state instead of drifting into plausible-sounding invented behavior.

````text
You are an autonomous senior engineering agent taking ownership of the GitHub
repository "Real-Time-Stablecoin-Payout-Risk-Scoring-System" (owner: qjmre23).
Your job spans security remediation, dependency/build repair, bug fixes, data
pipeline expansion, machine-learning methodology correction, backend
productionization, and a brand-new advanced web frontend. This is a large,
multi-session task. Work in the numbered phases below, in order, and do not
skip Phase 0.

================================================================================
GROUND RULES — READ BEFORE DOING ANYTHING (apply to every phase below)
================================================================================

1. VERIFY, DO NOT ASSUME. Before you describe what a file does, open it and
   read it. Before you claim a bug is fixed, run the code or the relevant
   test. Before you cite an Etherscan API parameter or endpoint name, confirm
   it against the live official documentation at https://docs.etherscan.io
   (if you have live web/browser access in this environment) or, if you do
   not have web access, treat the endpoint names, parameters, and base URL
   ALREADY PRESENT in this codebase (main.py, wallet_check.py — currently
   `https://api.etherscan.io/v2/api`, action=tokentx, action=txlist,
   action=txlistinternal, module=account, module=contract, module=gastracker,
   module=stats) as your only trusted reference, and add a clearly marked
   `# TODO(verify-live): confirm current Etherscan docs before relying on this`
   comment next to anything you cannot verify. Never invent an endpoint,
   field name, or response schema that you have not seen either in this
   codebase or in documentation you actually fetched.

2. NEVER FABRICATE METRICS. If you cannot get a model past 90% on a rigorous,
   leakage-free held-out test set, report the real number you achieved,
   explain why, and propose next steps. A fabricated or leakage-inflated
   "90%+" is worse than an honest 78% — it will get relied on for a system
   that blocks real financial transactions. Every accuracy/F1/precision/
   recall number that ends up in documentation or commit messages must come
   from a script you actually ran, and that script (or its output log) must
   be committed alongside the claim so it is independently reproducible.

3. NEVER COMMIT SECRETS. No API keys, database URLs, private keys, tokens,
   or credentials in any file that is or will be tracked by git — not even
   "temporarily," not even in comments, not even in test fixtures. Use
   environment variables loaded via `.env` (gitignored) with a checked-in
   `.env.example` that has placeholder values only. Before every commit,
   mentally re-check: "does this diff contain anything that looks like a
   real credential?"

4. WORK INCREMENTALLY AND PRESERVE DATA. Do not delete existing datasets,
   models, or wallet pools outright. When restructuring, move/archive first,
   confirm the new pipeline reproduces equivalent or better results, and only
   then remove the old artifacts from active use (and from git tracking,
   per Phase 1).

5. PREFER SMALL, REVIEWABLE COMMITS over one giant commit. Use clear commit
   messages describing WHAT changed and WHY. Open work as a feature branch
   (e.g. `fix/security-and-ml-integrity`, `feat/admin-console-ui`) rather
   than committing directly to main, unless the environment gives you no
   branching capability, in which case say so explicitly in your final report.

6. AT THE END OF EVERY PHASE, produce a short written report appended to
   `IMPLEMENTATION_LOG.md` (create it if it does not exist) stating: what you
   changed, what you verified by actually running it, what you could not
   verify and why, and any new TODOs or risks you introduced or discovered.
   This log is the record a human reviewer will read first — it must be
   honest about limitations, not just a list of accomplishments.

7. RESPECT ETHERSCAN'S TERMS OF SERVICE AND RATE LIMITS at all times. Use
   only the official documented API with a valid API key loaded from an
   environment variable. Do not scrape pages in ways that violate Etherscan's
   terms. Respect whatever rate limit applies to the API key tier in use
   (implement exponential backoff and honor any rate-limit response codes/
   headers Etherscan returns) rather than hardcoding a guessed delay.

8. DEFINE "ACCURACY" CAREFULLY. This dataset has severe class imbalance
   (label distribution documented in the repo's own README as roughly
   73.8% unknown/-1, then heavily skewed toward the safe class among labeled
   rows). A model that always predicts "safe" could score a high raw accuracy
   number while catching zero fraud. Wherever this prompt or any project
   document says "≥90% accuracy," the actual target metric set is:
     - Macro-averaged F1 ≥ 0.90 across the labeled classes (safe / malicious
       / poisoned), computed ONLY on a held-out test set that was never used
       for training, oversampling, scaling, or hyperparameter selection.
     - Recall on the malicious class ≥ 0.90 and recall on the poisoned class
       ≥ 0.90 specifically (a missed fraud case is far more costly than a
       false alarm in this domain — report both and do not let overall
       macro-F1 mask a weak fraud-recall number).
     - Report precision, recall, F1 per class, plus a full confusion matrix,
       for every trained token model, in a committed results file
       (`docs/model_performance/<token>_report.md` or similar), generated by
       a script, not hand-written.
   If after honest effort (better features, more data, tuned
   hyperparameters, ensembling) you still cannot reach these targets for a
   given token, document the actual achieved numbers and the specific
   bottleneck (e.g. "USDP has only 340 labeled rows total; recall on the
   poisoned class is data-limited, not model-limited") rather than silently
   lowering the bar or reporting a leakage-inflated number.

================================================================================
PHASE 0 — READ-ONLY AUDIT (produce AUDIT.md, make zero code changes yet)
================================================================================

Before changing anything, re-verify the following known issues yourself by
reading the actual current files (line numbers may have shifted since this
prompt was written — locate by content, not blindly by line number), and add
anything else you find. Write your findings to a new `AUDIT.md` at repo root.

Known issues to re-verify:
  a) main.py: hardcoded Etherscan API keys in `API_KEY` and the
     `VERSION_API_KEYS` dict near the top of the file.
  b) wallet_check.py: a separate hardcoded `API_KEY` constant.
  c) .env committed to the repository containing a real `DATABASE_URL`,
     despite `.gitignore` listing `.env`.
  d) gnn_model.py: `GCNFraudDetector`, `GATFraudDetector`,
     `GraphSAGEFraudDetector` classes inheriting from `nn.Module` where `nn`
     comes from a conditionally-imported `torch` that is not in
     requirements.txt — confirm this crashes `import gnn_model` in an
     environment without torch installed, by actually attempting the import
     in a clean virtualenv without torch.
  e) train_ml.py: confirm whether oversampling (`resample(...)`) and
     `StandardScaler.fit_transform(...)` currently happen before or after
     `train_test_split(...)`. If before (as last verified), this is a data
     leakage bug — confirm and document exact line numbers as they currently
     stand.
  f) requirements.txt completeness: attempt a clean
     `pip install -r requirements.txt` in an isolated virtualenv, then try to
     `import api, dashboard, gnn_model, deep_model, graph_engine,
     stream_listener` (each independently) and record every ImportError.
  g) db.py: check for corrupted/mixed line endings or encoding issues.
  h) Confirm whether `backup models/` and `datasets deprecated/` (or their
     current equivalents) are tracked by git despite matching a
     `.gitignore` pattern (`*.pkl`, `*.csv`) — run `git check-ignore -v` or
     equivalent on a sample file inside each to confirm they were force-added.
  i) Confirm there is no CI workflow (`.github/workflows/`), no Dockerfile,
     no pytest configuration, and enumerate the `test_*.py` files that exist
     but are not wired into anything.
  j) Read every loose root-level markdown doc (CRITICAL_FIX_SUMMARY.md,
     MULTI_TOKEN_IMPLEMENTATION.md, MULTI_TOKEN_SETUP_COMPLETE.md,
     TOKEN_DETECTION_FIX.md, TOKEN_EXPANSION_README.md,
     TOKEN_SPECIFIC_RULES.md, WALLET_CHECK_USAGE_GUIDE.md) and summarize what
     each documents, so nothing gets lost when they're consolidated in
     Phase 9.
  k) Actively look for anything NOT listed above: run a secret-scanning tool
     (e.g. gitleaks, trufflehog, or a manual regex sweep for patterns like
     API keys, AWS-style keys, private key hex strings, JWT-looking tokens,
     `postgres://`/`postgresql://` URLs with embedded passwords) across the
     full git history, not just the current working tree, since a key
     removed from HEAD is still recoverable from history until Phase 1's
     history-scrub step runs.

Do not proceed to Phase 1 until AUDIT.md exists and is committed.

================================================================================
PHASE 1 — CRITICAL SECURITY REMEDIATION (P0, blocking, do this first)
================================================================================

1. Immediately replace every hardcoded Etherscan API key in main.py and
   wallet_check.py with `os.getenv("ETHERSCAN_API_KEY_V0")` /
   `..._V1` / `..._V2` / `..._V3` / `..._V4` (or a single
   `ETHERSCAN_API_KEY` if per-version keys turn out to be unnecessary —
   check whether the per-version split in VERSION_API_KEYS is load-balancing
   across separate free-tier keys to dodge rate limits, and if so, preserve
   that pattern but source every key from the environment).

2. Create `.env.example` at repo root with placeholder values only, e.g.:
     ETHERSCAN_API_KEY_V0=your_etherscan_api_key_here
     ETHERSCAN_API_KEY_V1=your_etherscan_api_key_here
     ETHERSCAN_API_KEY_V2=your_etherscan_api_key_here
     ETHERSCAN_API_KEY_V3=your_etherscan_api_key_here
     ETHERSCAN_API_KEY_V4=your_etherscan_api_key_here
     DATABASE_URL=postgresql://user:password@host:5432/dbname
     ALCHEMY_WS_URL=wss://your-provider-websocket-url-here
     STREAM_ALERT_THRESHOLD=0.75
   Never put a real value in this file.

3. Confirm `.env` is in `.gitignore` (it already is, per the current file —
   verify it stays that way) AND confirm it is untracked going forward:
   `git rm --cached .env` if it is still tracked.

4. Scrub the leaked secrets from git history entirely, not just from the
   current HEAD. Use `git filter-repo` (preferred) or the BFG Repo-Cleaner
   to remove `.env` and any commit content containing the leaked API keys
   from the full history, then document in IMPLEMENTATION_LOG.md that a
   force-push / history rewrite occurred and that all collaborators must
   re-clone. If you do not have the ability to force-push or rewrite remote
   history in this environment, clearly state that in the log as an
   OUTSTANDING MANUAL STEP the repository owner must perform themselves,
   and do not claim it as done if it isn't.

5. Add a secret-scanning pre-commit hook (e.g. via the `pre-commit` framework
   with `gitleaks` or `detect-secrets`) so this class of bug cannot recur,
   and wire the same scanner into CI (Phase 9) so a PR containing a secret
   fails the build.

6. Note explicitly in IMPLEMENTATION_LOG.md that rotating the actual
   Etherscan keys and the database password in their respective provider
   dashboards is a MANUAL action outside the agent's capability (unless you
   are given API/CLI access to actually do it) — flag it as the single
   highest-priority action item for the human repository owner, first line
   of the report.

================================================================================
PHASE 2 — BUILD SYSTEM & DEPENDENCY REPAIR
================================================================================

1. Rebuild requirements into a clean, layered dependency structure. Recommend
   using `pyproject.toml` with optional extras (or, if the environment
   prefers plain pip files, split into):
     - `requirements.txt` — core, always-needed: pandas, numpy, requests,
       beautifulsoup4, scikit-learn, psycopg2-binary, python-dotenv,
       python-json-logger, pydantic.
     - `requirements-ml.txt` — xgboost, lightgbm, optuna (for tuning,
       Phase 5), joblib.
     - `requirements-api.txt` — fastapi, uvicorn[standard], websockets,
       aiohttp, slowapi (or another FastAPI-compatible rate limiter).
     - `requirements-dashboard.txt` — streamlit, plotly, networkx (only if
       you are keeping the Streamlit dashboard as a secondary/internal
       tool alongside the new web UI from Phase 7 — see that phase for the
       recommendation on whether to keep or retire dashboard.py).
     - `requirements-deep.txt` — torch, torch-geometric, tensorflow (heavy,
       genuinely optional; document the CUDA/CPU install caveats for
       torch-geometric, which has notoriously fragile installation
       requirements tied to exact torch + CUDA versions — do not just list
       "torch-geometric" with no version pin and call it done).
   Pin every dependency to a specific tested version (`==`), not a bare
   package name, so builds are reproducible.

2. Fix gnn_model.py so it is safely importable with or without torch
   installed. The unconditional `class Foo(nn.Module):` pattern must not
   execute when torch is missing. Two acceptable approaches:
     a) Guard the entire class definition inside `if HAS_TORCH:` and provide
        a lightweight stub class (or `None`) in the `else` branch, with every
        call site checking `HAS_TORCH` / `gnn_model.GCNFraudDetector is not
        None` before instantiating.
     b) Restructure into a factory function `build_gcn_model(...)` that
        imports torch lazily inside the function body and raises a clear,
        actionable `ImportError("Install torch and torch-geometric to use
        GNN models: pip install -r requirements-deep.txt")` only when
        actually called, not at module import time.
   Whichever you choose, add a unit test that imports gnn_model.py in a
   torch-free environment (mock/skip torch, or run this specific test in a
   virtualenv without torch installed) and asserts the import succeeds and
   any attempt to instantiate a GNN model raises the clear ImportError
   above rather than a bare NameError.

3. Apply the same "must be safely importable without optional heavy deps"
   audit to deep_model.py, dashboard.py (streamlit), api.py (fastapi), and
   stream_listener.py (websockets/aiohttp) — each currently has partial
   `HAS_X` guards; verify every one of them is complete and consistent, and
   that no top-level, unconditional reference to an optionally-imported name
   exists anywhere in the file.

4. Normalize line endings repo-wide. Add a `.gitattributes` file enforcing
   `* text=auto eol=lf`, then run the normalization once
   (`git add --renormalize .`) so files like db.py stop containing literal
   `\r\r` sequences. Run `black` (or `ruff format`) and `ruff check --fix`
   (or `flake8` + `isort` if you prefer that toolchain) across the whole
   Python codebase for consistent formatting and import ordering, as a
   dedicated, isolated commit separate from behavioral changes so the diff
   is reviewable.

5. Add a `Dockerfile` for the API service and a `docker-compose.yml` that
   brings up: the FastAPI service, a Postgres container (for db.py's feature
   cache), and a Redis container (for the real caching layer — see Phase 6,
   item 4, which replaces the README's old "Redis-like caching layer"
   aspiration with an actual Redis dependency). Include a `docker-compose
   up` smoke-test instruction in the README's quickstart.

6. Move `backup models/` (27MB of committed `.pkl` files) and
   `datasets deprecated/` (4MB of committed CSVs) out of active git tracking.
   Recommended approach: stop tracking them going forward
   (`git rm -r --cached "backup models" "datasets deprecated"`, keep the
   files on disk locally, confirmed excluded by the existing `.gitignore`
   patterns), then either (a) publish the current best model artifacts as
   GitHub Release assets so they remain downloadable without bloating clone
   size, or (b) introduce DVC (Data Version Control) or Git LFS if the team
   wants versioned binary tracking going forward. Document whichever you
   choose in README under a "Model & Dataset Artifacts" section, and note
   that removing large binaries from *future* commits does not shrink
   *historical* repo size — that requires the same history-rewrite tooling
   as Phase 1's secret scrub, and should be scheduled as one combined
   history-cleanup pass to avoid rewriting history twice.

================================================================================
PHASE 3 — TARGETED BUG FIXES
================================================================================

Fix each of the following, and for each one, add or update a regression test
under a proper `tests/` directory (moving/consolidating the existing loose
`test_*.py` files from repo root into `tests/`, updating imports as needed)
that would have caught the bug:

1. wallet_check.py token detection (3-level fallback: manual override →
   tokenSymbol → contractAddress) — this was previously fixed per
   CRITICAL_FIX_SUMMARY.md / TOKEN_DETECTION_FIX.md. Re-verify it still
   works correctly for the specific case those docs describe (empty
   `tokenSymbol` field, valid `contractAddress`), and add a permanent
   regression test using a mocked/fixture Etherscan response with an empty
   `tokenSymbol` to lock this behavior in going forward.

2. train_ml.py leakage fix (this is also covered in depth in Phase 5, but
   the mechanical code fix belongs here): reorder operations so that
   `train_test_split` happens FIRST (on raw, non-oversampled, non-scaled
   data), and both `StandardScaler.fit` and any oversampling/resampling are
   fit ONLY on the resulting training fold, then applied (`.transform`, not
   `.fit_transform`) to the validation and test folds. See Phase 5 for the
   full methodology this must satisfy.

3. Any other bugs discovered during Phase 0's audit that weren't already
   listed above — fix each with the same test-first discipline: write a
   failing test that reproduces the bug, then fix the code until it passes.

4. Consolidate the seven loose root-level markdown fix-summary docs
   (CRITICAL_FIX_SUMMARY.md, MULTI_TOKEN_IMPLEMENTATION.md,
   MULTI_TOKEN_SETUP_COMPLETE.md, TOKEN_DETECTION_FIX.md,
   TOKEN_EXPANSION_README.md, TOKEN_SPECIFIC_RULES.md,
   WALLET_CHECK_USAGE_GUIDE.md) plus `pipeline.txt`, `structure.txt`,
   `structure copy.txt` into an organized `docs/` folder: e.g.
   `docs/history/` for the historical fix write-ups (kept for context, not
   deleted — they contain real debugging history worth preserving) and a
   single current `docs/ARCHITECTURE.md` for anything still accurate and
   relevant today. Remove the now-redundant content from repo root.

================================================================================
PHASE 4 — ETHERSCAN DATA PIPELINE HARDENING & EXPANSION
================================================================================

Goal: more data, higher-quality labels, and richer features, sourced
correctly and respectfully from Etherscan's actual documented API.

1. Before writing any new Etherscan integration code, fetch and read the
   current official documentation at https://docs.etherscan.io (if you have
   live web access). Confirm: the current base URL and whether the
   multi-chain "V2 unified API" pattern already used in this codebase
   (`https://api.etherscan.io/v2/api` with a `chainid` parameter) is still
   the recommended integration path, the current rate limits per API key
   tier (free vs paid), and the exact parameter names for every endpoint you
   plan to use below. If you do not have live web access, use ONLY the
   endpoint/parameter patterns already proven working elsewhere in this
   codebase (`action=tokentx`, `action=txlist` under `module=account`, etc.)
   as your reference, and clearly flag with a TODO comment any new endpoint
   you add whose exact parameters you could not verify firsthand.

2. Expand feature extraction to pull additional Etherscan data already
   available via documented endpoints the codebase does not yet use, such as:
     - Internal transactions (`action=txlistinternal`) — capture contract-
       mediated fund movement the current top-level `txlist`/`tokentx` calls
       miss.
     - Contract verification status of counterparty addresses
       (`module=contract`, `action=getsourcecode` /
       `action=getcontractcreation`) — an unverified, freshly-deployed
       counterparty contract is a meaningfully different risk signal than a
       verified, long-standing one; add this as a new feature column
       (e.g. `counterparty_contract_verified`, `counterparty_contract_age_days`).
     - Gas price/gas used anomalies relative to the wallet's own historical
       baseline and relative to network conditions at the time
       (`module=gastracker` / `module=stats`), as an additional bot-detection
       signal beyond the existing `tx_per_hour`/`avg_time_between_tx_sec`
       heuristics.
   For each new feature, document it in a `docs/FEATURES.md` reference
   (feature name, source endpoint, computation logic, rationale) so future
   contributors understand why it exists, and add it consistently across
   `main.py`'s feature extraction, `wallet_check.py`'s runtime feature
   generation, and `train_ml.py`'s `ensure_features()` so training and
   inference schemas never drift apart (a schema mismatch between training
   and inference is one of the most common causes of silent accuracy
   collapse in production ML systems — treat schema parity as a hard
   invariant, and add an automated test asserting the training feature
   column list and the runtime feature column list are identical).

3. Expand the labeled dataset responsibly:
     - Widen and diversify the `SEEDS_V0`–`SEEDS_V4` seed wallet lists in
       main.py, sourcing new seeds from Etherscan's own publicly documented
       address labeling / name-tag information where accessible through the
       official API or site in a ToS-compliant way, and from established,
       publicly published, well-known compliance reference lists such as
       the U.S. Treasury OFAC SDN list's published cryptocurrency addresses
       (a standard, legitimate reference used broadly in AML/fraud-detection
       tooling; treat these strictly as label sources, not as an excuse to
       bypass the API-based feature extraction pipeline).
     - Increase wallet pool sizes for chronically underrepresented tokens
       (per the current README's own numbers, USDP/TUSD have far fewer
       labeled rows than USDT) so no token model is trained on a dataset too
       small to support a statistically meaningful held-out test set — a
       reasonable floor to target is at least several hundred labeled rows
       per class per token before trusting any reported metric for that
       token; if a token cannot reach that floor, say so explicitly rather
       than reporting a metric computed on a handful of test rows.
     - When expanding `expand_wallets()`'s crawl, keep respecting the
       existing 5-minute per-version cap and add configurable, documented
       rate-limit backoff (read Etherscan's actual rate-limit response
       signal — typically an HTTP 429 or a specific JSON error message field
       — rather than a fixed `time.sleep()` guess) so larger crawls don't
       get the API key throttled or banned.

4. Add a `GroupKFold`-aware wallet identity check: because a single wallet
   address can legitimately appear in more than one version's dataset
   (e.g. flagged safe in V0 but later reclassified in V3), add a dedup/
   consistency pass during dataset assembly in `train_ml.py` that groups by
   wallet address, not just by row, before any split — this is essential
   groundwork for Phase 5's leakage-free split and is listed here because
   it's fundamentally a data-pipeline concern (which rows even exist to be
   split) as much as a modeling concern.

================================================================================
PHASE 5 — ML METHODOLOGY OVERHAUL (this is how you honestly reach ≥90%)
================================================================================

The current pipeline's biggest problem is not "not enough data" — it's that
its evaluation methodology cannot be trusted, per the leakage issues found in
Phase 0/1. Fix the methodology first; only then will more data and better
features actually translate into a trustworthy, reportable number.

1. Correct split order (mandatory, non-negotiable):
   Load raw data → group by wallet address → split into train / validation /
   test by wallet GROUP (not row), e.g. 70% / 15% / 15%, stratified by label
   where feasible → ONLY THEN fit the StandardScaler on the training fold
   and `.transform()` (never `.fit_transform()`) the validation and test
   folds → ONLY THEN apply oversampling/class-balancing to the TRAINING
   fold alone (validation and test folds must reflect real-world class
   distribution, untouched by oversampling, so the reported metrics mean
   something) → train → evaluate on validation (for model/hyperparameter
   selection) → report FINAL numbers on the test fold, which must be
   touched exactly once, at the very end, never used for any tuning
   decision.

2. Replace naive row-duplication oversampling with either:
     - `imblearn`'s `SMOTE` / `SMOTENC` (proper synthetic minority
       oversampling operating in feature space, fit on the training fold
       only), or
     - Class-weighted loss (already partially present via
       `class_weight="balanced"` / the manual `TOKEN_CONFIG` weights) used
       INSTEAD of oversampling, avoiding the duplication-leakage risk
       entirely.
   Either is acceptable; naive `resample()`-based duplication before a split
   is not.

3. Replace the single 80/20 train/val split currently used for model
   selection with proper k-fold (e.g. `StratifiedGroupKFold`, k=5) cross-
   validation on the training+validation portion, reporting mean ± std of
   macro-F1 and per-class recall across folds — a single split's F1 number
   is noisy, especially on the smaller-token datasets, and can make a model
   look better or worse than it really is purely by chance of which rows
   landed where.

4. Add real hyperparameter tuning (Optuna is a good fit given the existing
   RF/XGBoost/LightGBM setup) with the cross-validation macro-F1 (with the
   fraud-class recall floor from the Ground Rules section) as the
   optimization objective, not raw accuracy. Budget a reasonable number of
   trials per token (e.g. 50-100) given the dataset sizes involved — this
   doesn't need to be exhaustive, but "auto" model selection choosing
   between three untuned default-hyperparameter models (the current
   behavior) leaves real performance on the table.

5. Consider a stacked/ensemble final model (e.g. combining the tuned RF,
   XGBoost, and LightGBM predictions, plus the existing rule-based engine's
   output as a feature) rather than picking only the single best of the
   three — ensembling is a legitimate, non-hacky way to close the last few
   points toward the 90% target, as long as it's evaluated with the same
   leakage-free held-out test discipline as everything else.

6. For every trained token model, generate and commit:
     - `docs/model_performance/<token>_report.md`: precision/recall/F1 per
       class, confusion matrix, ROC-AUC per class (one-vs-rest), the exact
       train/val/test row counts and class distributions used, and the
       cross-validation mean±std.
     - The script that generated that report (e.g.
       `scripts/evaluate_model.py --token usdt`), so any reviewer can
       re-run it and get the same numbers from the same data.
   Do not hand-write these numbers into README or IMPLEMENTATION_LOG.md —
   generate them from code and either paste the actual script output or
   embed the report file, so the numbers are auditable.

7. If, after all of the above, a given token's model genuinely cannot reach
   the ≥0.90 macro-F1 / ≥0.90 fraud-recall targets, do not lower the bar
   silently — document the real achieved numbers, identify the likely cause
   (data volume, label noise, feature ceiling, genuinely harder attack
   pattern for that token type), and propose a concrete next step (e.g.
   "USDP needs at least 3x more labeled malicious examples before recall
   will improve meaningfully; recommend prioritizing seed expansion for
   this token in the next data-collection pass").

================================================================================
PHASE 6 — BACKEND / API PRODUCTIONIZATION (api.py)
================================================================================

Extend the existing FastAPI service rather than replacing it with a new
language/framework — it already implements the right endpoints
(`/score_wallet`, `/health`, `/batch_score`, `/get_model_info`) and updating
the old README's "Go (planned)" framing to reflect this reality is itself
part of Phase 9's documentation rewrite. Specifically add:

1. Authentication: API-key-based auth (a simple `X-API-Key` header checked
   against a stored, hashed set of valid keys — do not store plaintext API
   keys even for consumers of your own API) or JWT-based auth if there's a
   multi-tenant admin-console user system (see Phase 7) that needs real user
   sessions rather than static keys. Document clearly which one you chose
   and why.

2. Rate limiting on all public endpoints (e.g. via `slowapi`), with limits
   configurable via environment variables, and clear 429 responses.

3. A WebSocket endpoint (`/ws/live-alerts` or similar) inside `api.py` that
   bridges `stream_listener.py`'s real-time scored-transaction output to
   connected frontend clients, so the Phase 7 web UI's live feed has a
   single, authenticated, first-party channel to connect to rather than
   talking to `stream_listener.py` directly.

4. Real caching: replace the README's old "Redis-like caching layer" future-
   work item with an actual Redis integration (via `redis-py` or
   `aioredis`), used both for the existing feature-cache role currently
   served only by Postgres in `db.py` (Redis as a fast layer in front of
   Postgres, not a replacement for it — Postgres remains the durable store)
   and for API response caching of recently-scored wallets within a short
   TTL to protect against duplicate rapid re-scoring of the same address.

5. Structured logging (JSON logs via `python-json-logger` or similar) and a
   `/metrics` Prometheus-compatible endpoint exposing request counts,
   latency histograms, model-inference latency specifically (distinct from
   total request latency, so cache-hit vs cache-miss vs live-Etherscan-
   fallback latency are all separately visible — this maps directly onto
   the existing README's stated <200ms latency target and its cache-hit vs
   cache-miss distinction).

6. Robust error handling: typed exception classes (e.g.
   `TokenNotDetectedError`, `ModelNotAvailableError`, `EtherscanAPIError`,
   `RateLimitExceededError`) mapped to specific, documented HTTP status
   codes and structured JSON error bodies, replacing any bare/generic
   exception handling currently present.

7. A proper `/health` check that actually verifies DB connectivity and that
   at least the core trained models can be loaded, not merely a static
   "ok" string — the current `HealthResponse` model already has a
   `graph_engine_available` field; extend this pattern to genuinely probe
   each dependency.

8. CORS configuration appropriate for the Phase 7 frontend's origin(s),
   configurable via environment variable rather than hardcoded.

Decide explicitly whether `dashboard.py` (Streamlit) should be kept as an
internal/ops tool alongside the new Phase 7 web UI, or retired once the new
UI covers its functionality — document the decision and reasoning in
IMPLEMENTATION_LOG.md rather than leaving two competing, half-documented UIs.

================================================================================
PHASE 7 — ADVANCED WEB UI: "BLOCKCHAIN SECURITY ADMIN CONSOLE"
================================================================================

Build a new, dedicated, production-quality web frontend — this is a first-
class deliverable, not an afterthought bolted onto the Streamlit dashboard.

TECH STACK (use this unless you have a strong, documented reason to deviate):
  - React 18+ with TypeScript in strict mode, via Vite (fast dev/build,
    simpler than Next.js for a pure SPA admin console with no SEO needs).
  - Tailwind CSS + shadcn/ui component primitives for a consistent,
    accessible base component set that's easy to theme.
  - Recharts or visx for time-series/statistical charts (risk score
    distributions, alert volume over time, model performance trends).
  - react-force-graph or Cytoscape.js for the wallet-cluster network graph
    visualization (surfacing graph_engine.py's clustering output visually —
    this is explicitly called out in the original README as a "key
    strength" of the system and currently has zero visual representation
    anywhere).
  - TanStack Query (React Query) for server state/data fetching against the
    Phase 6 FastAPI backend, plus a native WebSocket hook for the live
    alert feed.
  - Zustand (or React context, if you prefer minimal dependencies) for
    lightweight client-side UI state.
  - Vitest for unit tests, Playwright for a small set of critical-path e2e
    tests (wallet lookup flow, live-feed connection, alert acknowledgment).

VISUAL DESIGN DIRECTION ("highly advanced blockchain security admin theme"):
  - Dark-first, near-black/deep-navy base (e.g. `#0a0e17` / `#0d1117`-family
    background), NOT a generic dark-mode toggle on a light-first design —
    design dark-first, offer a light theme as secondary if time allows.
  - A restrained neon/cyber accent palette used purposefully, not
    decoratively: cyan or electric-blue for neutral/info UI chrome, amber/
    orange for REVIEW-state risk, red for BLOCK-state risk, green for
    ALLOW-state — consistent everywhere a decision is shown (cards, badges,
    graph node colors, chart series).
  - Glassmorphic elevated cards (subtle translucency + blur + thin
    luminous border) for panel/widget containers, used consistently, not on
    every single element — reserve it for primary dashboard cards so it
    reads as intentional rather than noisy.
  - Monospace font (e.g. JetBrains Mono, IBM Plex Mono, or similar) for all
    wallet addresses, transaction hashes, and raw data values, contrasted
    against a clean sans-serif (e.g. Inter) for UI labels/body text — this
    single choice does more than almost anything else to make an interface
    read as a "security tool" rather than a generic dashboard template.
  - Subtle live-data motion: animated risk-score gauges/needles, a gently
    ticking "transactions processed" counter, a pulsing indicator on live
    WebSocket connection state — motion should communicate "this system is
    alive and watching in real time," but must be subtle and non-distracting,
    respecting `prefers-reduced-motion`.
  - General aesthetic reference point (for inspiration/genre only — do not
    copy any specific company's actual branding, logos, or proprietary
    layouts): the visual register of professional blockchain-forensics/SOC
    tooling — dense, data-rich, monospace-heavy, dark, purposeful use of
    red/amber/green status color, not the visual register of a generic
    consumer SaaS dashboard.
  - Maintain WCAG AA contrast ratios even within the dark/neon palette —
    verify actual contrast ratios for text-on-background and status-badge
    combinations, don't just eyeball it.
  - Fully responsive: the console must be genuinely usable on a laptop
    screen down to a tablet width at minimum; a security operator should be
    able to triage an alert from a tablet.

REQUIRED PAGES / VIEWS:
  1. Command Center (default landing page): system-wide stats (wallets
     scored today, current ALLOW/REVIEW/BLOCK rate, active WebSocket
     connection status, model health per token), a live-updating recent-
     alerts feed, and a compact multi-token risk heatmap.
  2. Wallet Investigate: a search/lookup box for a wallet address, showing
     the full scoring breakdown (probabilities per class, decision,
     confidence, which rule fired if a rule fired vs. which ML model
     scored it, matched feature values that drove the decision, and — if
     graph_engine.py has connectivity data for it — its nearest-neighbor
     wallet cluster).
  3. Live Transaction Stream: a real-time, filterable table (by token, by
     decision, by risk-score threshold) fed by the Phase 6 WebSocket
     endpoint, with the ability to click through to the Wallet Investigate
     view for any row.
  4. Wallet Network Graph: an interactive force-directed graph visualizing
     wallet clusters and their interconnections (using graph_engine.py's
     output), with node color mapped to risk decision and node size mapped
     to some meaningful metric (e.g. transaction volume or graph
     centrality) — this directly surfaces the "Graph Intelligence" the
     original README calls the system's key differentiator, which
     currently has no visual representation anywhere in the project.
  5. Alerts & Case Management: a list/queue of BLOCK and REVIEW decisions
     awaiting human review, with the ability to mark an alert
     reviewed/dismissed/escalated (persisted via a new backend
     endpoint/table — extend db.py's schema for this), and a simple audit
     trail of who reviewed what and when.
  6. Model Performance & Analytics: per-token model cards showing the
     Phase 5 evaluation metrics (precision/recall/F1/confusion matrix,
     pulled from the committed `docs/model_performance/` reports or a live
     endpoint exposing the same data), plus a token-coverage matrix
     (trained vs. watch-only, matching the README's existing 54-token
     breakdown) and links to trigger a documented retraining workflow.
  7. Settings: environment/connection status indicators (Etherscan API
     reachability, DB connectivity, WebSocket provider status), with any
     API keys shown fully masked (e.g. `••••••••••••WIPY`) and never
     retrievable in plaintext through the UI once saved.

Wire the frontend's data layer entirely against the Phase 6 FastAPI
endpoints and WebSocket channel — do not have the frontend call Etherscan
directly, and do not duplicate scoring logic in the frontend; the backend
remains the single source of truth for every risk decision.

Add a `frontend/README.md` covering local dev setup (`npm install`,
`npm run dev`), build, and how the dev server proxies API calls to the
Phase 6 backend (e.g. via a Vite proxy config pointing at
`http://localhost:8000` in development).

================================================================================
PHASE 8 — REAL-TIME STREAMING INTEGRATION
================================================================================

1. Confirm stream_listener.py's `RealTimeProcessor` correctly feeds into the
   Phase 6 `/ws/live-alerts` WebSocket endpoint (rather than existing as an
   isolated, undocumented module as it currently does) — this is the wiring
   that makes Phase 7's "Live Transaction Stream" page actually live.

2. Load `provider_url` (currently referenced as an Alchemy/Infura WebSocket
   endpoint) from an environment variable (`ALCHEMY_WS_URL` /
   `INFURA_WS_URL`), never hardcoded, consistent with Phase 1's secret
   handling.

3. Add integration tests for the reconnect/exponential-backoff logic already
   present in `ChainStream` (simulate a dropped connection and assert
   reconnection occurs within the configured backoff schedule) and for
   `StreamBuffer`'s time/size-based batch flushing (assert a batch flushes
   at both the configured size limit and the configured timeout, whichever
   comes first).

4. Ensure alert generation from the stream (`alert_threshold`, currently
   configurable via `STREAM_ALERT_THRESHOLD`) writes to the same
   alerts/case-management store the Phase 7 "Alerts & Case Management" page
   reads from, so a live-stream-triggered alert and a manually-scored
   BLOCK/REVIEW decision both surface through the same unified queue rather
   than two disconnected alert systems.

================================================================================
PHASE 9 — TESTING, CI/CD, OBSERVABILITY
================================================================================

1. Consolidate all test_*.py files into a proper `tests/` directory
   (`tests/unit/`, `tests/integration/`), configure `pytest` via
   `pyproject.toml` or `pytest.ini`, and ensure `pytest` runs cleanly with
   zero import errors from repo root.

2. Add a GitHub Actions workflow (`.github/workflows/ci.yml`) that on every
   push/PR: installs dependencies, runs `ruff`/`black --check` (lint/format
   check), runs `mypy` (or at minimum type-checks the newer/rewritten
   modules if full-repo typing isn't realistic in one pass), runs the full
   `pytest` suite, and runs the secret-scanning tool from Phase 1 — and
   fails the build on any of these failing.

3. Add a second workflow (or a job in the same one) for the `frontend/`
   package: `npm ci`, `npm run lint`, `npm run build`, and the Vitest unit
   suite.

4. Add basic structured logging and the `/metrics` endpoint from Phase 6 as
   the observability baseline — full tracing/APM integration is a
   reasonable "next evolution" item to document rather than fully build in
   this pass, but say so explicitly rather than silently skipping it.

================================================================================
PHASE 10 — FINAL DOCUMENTATION REWRITE
================================================================================

1. Rewrite README.md from scratch as a single, internally consistent
   document (removing the current duplicated/contradictory content) that
   accurately describes the system AS IT NOW EXISTS after all the above
   phases — including the FastAPI backend, the new frontend, Redis, the
   WebSocket live-alert channel, and the corrected ML methodology and its
   real, reproducible performance numbers. Remove any remaining references
   to the old "Go (planned)" API or "Browser Extension" client unless you
   actually built those (you are not building either in this prompt — the
   FastAPI backend and the new React admin console are the real client/
   server layers going forward).

2. Move this build prompt itself into `docs/AGENT_BUILD_PROMPT.md` once the
   work it describes is substantially complete, and replace it in the live
   README with a short "Engineering History" section summarizing what was
   done and linking to `IMPLEMENTATION_LOG.md` and `AUDIT.md` for full
   detail — a finished project's README should describe the system, not
   carry a multi-thousand-word agent instruction set forever.

3. Ensure `docs/ARCHITECTURE.md`, `docs/FEATURES.md`, and the per-token
   `docs/model_performance/*.md` reports from earlier phases are all linked
   from the README's table of contents, so a new reader can navigate from
   README → any deeper doc within two clicks.

4. Do a final honest pass: read through every claim in the rewritten README
   and confirm each one against the actual current code/config/test output
   one more time before considering this prompt complete. If something in
   the README can't be verified against real, currently-running code, cut
   the claim or mark it explicitly as planned/future work, not shipped.

================================================================================
END OF PROMPT
================================================================================
````

---

## 🗂️ Original System Reference (kept for context — token list, decision logic, etc.)

The details below reflect the system's existing, real design (54 supported tokens, decision-engine thresholds, rule-based heuristics, weighted training strategy) and are the ground truth the agent prompt above should preserve and correct, not discard.

### Supported Tokens (54 total)
- **Trained (6):** USDT, USDC, DAI, BUSD, USDP, TUSD
- **Watch-only (48):** remaining stablecoins, DeFi, L2/native, wrapped, and meme tokens, plus native ETH (non-ERC20), detected via the 3-level fallback (manual override → `tokenSymbol` → `contractAddress`).

### Decision Logic (rules run before ML; ML applies token-type-aware thresholds)
```
1. Fetch features
2. Apply rule-based heuristics (new-wallet risk, spam pattern, dust-only
   activity, bot-speed transactions, dormant-wallet spikes, abnormal
   hourly rate) → if a rule fires, decide immediately
3. Otherwise, load the trained model for the token (or the token-type
   fallback thresholds for watch-only tokens) and classify:
     poisoned >= 0.5  → BLOCK
     malicious >= 0.8 → BLOCK
     malicious >= 0.5 → REVIEW
     else              → ALLOW
```

### Repository Layout (current, pre-Phase-9-cleanup)
```
main.py            # dataset generation (V0-V4, 54 tokens, Etherscan graph expansion)
train_ml.py         # RF/XGBoost/LightGBM training, per-token weighted datasets
wallet_check.py      # runtime scoring: rules + ML + token detection
stream_listener.py   # WebSocket live-transaction listener + buffered scoring
api.py               # FastAPI REST scoring service (undocumented in old README)
dashboard.py         # Streamlit visualization dashboard (undocumented in old README)
graph_engine.py       # NetworkX wallet-cluster graph intelligence
gnn_model.py          # PyTorch-Geometric GNN models (currently import-broken)
deep_model.py         # TensorFlow LSTM/Transformer sequence models
db.py                 # Postgres feature/label cache
scan_and_report.py    # dataset/model inventory utility
model_tester.py        # basic model-load sanity check
datasets/, models/, "public address dataset/", backups/, "backup models/",
"datasets deprecated/"   # generated/committed data & model artifacts
```

---

*This README was rewritten to serve as both accurate project documentation and
 the delivery vehicle for the agent build prompt above. All issues described as "verified" were confirmed against the actual repository contents at the time of writing, not inferred from prior documentation alone.*
