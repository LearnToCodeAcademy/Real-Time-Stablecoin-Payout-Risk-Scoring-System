"""Print the generated held-out performance report for a token model."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from risk_system.training import write_performance_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token", required=True, choices=["usdt", "usdc", "dai", "busd", "usdp", "tusd"])
    args = parser.parse_args()
    os.chdir(Path(__file__).resolve().parents[1])
    try:
        report = write_performance_report(args.token)
    except FileNotFoundError as exc:
        raise SystemExit(str(exc)) from exc
    print(report.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
