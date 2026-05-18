#!/usr/bin/env python3
"""Print Plutus Wire SQLite store status."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lib.local_store import connect_db, store_summary
from lib.store import DEFAULT_STATE_DIR


def main() -> int:
    parser = argparse.ArgumentParser(description="Print Plutus Wire DB status.")
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    args = parser.parse_args()

    conn = connect_db(args.state_dir.expanduser())
    try:
        print(json.dumps(store_summary(conn), ensure_ascii=False, indent=2))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
