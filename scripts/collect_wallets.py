"""Run a resumable real-Etherscan wallet collection from the command line."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from risk_system.collector import CollectionSettings, WalletCollector


def main() -> int:
    os.chdir(Path(__file__).resolve().parents[1])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=int, default=50_000, help="Wallet target, up to 1,000,000")
    parser.add_argument("--tokens", nargs="+", default=["USDT", "USDC"])
    parser.add_argument("--seed", action="append", default=[], help="Seed wallet; may be repeated")
    parser.add_argument("--job-id", help="Reuse an existing job id to resume its checkpoint")
    parser.add_argument("--neighbors", type=int, default=25)
    parser.add_argument("--transactions", type=int, default=100)
    args = parser.parse_args()
    settings = CollectionSettings(
        target_wallets=args.target,
        tokens=args.tokens,
        seed_wallets=args.seed,
        max_neighbors_per_wallet=args.neighbors,
        transactions_per_wallet=args.transactions,
        resume=True,
    )

    def progress(state) -> None:
        print(
            f"\r{state.status:10} discovered={state.discovered:,}/{args.target:,} "
            f"processed={state.processed:,} requests={state.requests:,} errors={state.errors:,}",
            end="",
            flush=True,
        )

    result = WalletCollector(settings, job_id=args.job_id, progress=progress).run()
    print("\n" + json.dumps(result.__dict__, indent=2))
    return 0 if result.status in {"success", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
