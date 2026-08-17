"""Train and activate a leakage-safe versioned token model."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from risk_system.training import ModelTrainer, TrainingOptions


def main() -> int:
    os.chdir(Path(__file__).resolve().parents[1])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--token", default="usdt", choices=["usdt", "usdc", "dai", "busd", "usdp", "tusd", "all"]
    )
    parser.add_argument("--model", default="auto", choices=["auto", "rf", "xgb", "lgb"])
    parser.add_argument("--estimators", type=int, default=300)
    parser.add_argument("--max-depth", type=int, default=16)
    parser.add_argument("--cv-folds", type=int, default=5)
    parser.add_argument(
        "--tuning-trials", type=int, default=0, help="Optuna trials; 50-100 is a thorough run"
    )
    args = parser.parse_args()
    options = TrainingOptions(
        token=args.token,
        model=args.model,
        estimators=args.estimators,
        max_depth=args.max_depth,
        cv_folds=args.cv_folds,
        tuning_trials=args.tuning_trials,
    )

    def progress(run) -> None:
        print(f"\r{run.progress:6.1%} {run.stage:18} {run.message}", end="", flush=True)

    result = ModelTrainer(options, progress=progress).execute()
    print("\n" + json.dumps(result.__dict__, indent=2))
    return 0 if result.status in {"success", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
