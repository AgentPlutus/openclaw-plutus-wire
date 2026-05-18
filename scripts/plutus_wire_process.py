#!/usr/bin/env python3
"""Build local Plutus Wire review cards from SQLite."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lib.local_store import connect_db
from lib.processor import build_review_package, write_review_package
from lib.store import DEFAULT_STATE_DIR, ensure_state_dirs


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Plutus Wire review cards.")
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    parser.add_argument("--run-id", help="Limit processing to one ingest run.")
    parser.add_argument("--limit", type=int, default=120, help="Maximum input posts.")
    parser.add_argument("--language", default="source", help="Review card language marker.")
    parser.add_argument("--print", action="store_true", help="Print the package JSON after writing it.")
    args = parser.parse_args()

    state_dir = args.state_dir.expanduser()
    ensure_state_dirs(state_dir)
    conn = connect_db(state_dir)
    try:
        package = build_review_package(
            conn,
            run_id=args.run_id,
            limit=args.limit,
            language=args.language,
        )
    finally:
        conn.close()

    paths = write_review_package(state_dir, package)
    print(f"plutus-wire: wrote {paths['latest_package_path']}")
    print(f"plutus-wire: wrote {paths['latest_cards_path']}")
    print(f"plutus-wire: review cards {package['card_count']}")
    if args.print:
        print(json.dumps(package, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
