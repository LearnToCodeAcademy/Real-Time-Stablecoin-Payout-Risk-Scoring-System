"""Sync explicitly risk-labeled rows from Etherscan's current Gas Guzzlers page."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from risk_system.reputation import sync_etherscan_gas_guzzler_labels


def main() -> int:
    os.chdir(Path(__file__).resolve().parents[1])
    print(json.dumps(sync_etherscan_gas_guzzler_labels(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
