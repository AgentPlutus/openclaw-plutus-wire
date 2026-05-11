#!/usr/bin/env python3
"""Run one Plutus Wire ingest tick."""

from __future__ import annotations

import argparse
import fcntl
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.opencli_call import find_opencli, opencli_version
from lib.source_registry import normalize_sources, source_by_name
from lib.store import DEFAULT_STATE_DIR, ensure_state_dirs, write_json


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_manifest(state_dir: Path, sources: list[str], dry_run: bool) -> dict[str, Any]:
    return {
        "run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "started_at": utc_now(),
        "dry_run": dry_run,
        "state_dir": str(state_dir),
        "opencli_path": find_opencli(),
        "opencli_version": opencli_version(),
        "adapter_version": "0.1.0a0",
        "sources": [
            {
                "name": name,
                "label": source_by_name(name).label,
                "adapter_command": source_by_name(name).adapter_command,
                "status": "planned" if dry_run else "not_implemented",
            }
            for name in sources
        ],
        "cloud_sync": {
            "enabled": False,
            "mode": "off",
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one Plutus Wire ingest tick.")
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    parser.add_argument("--source", action="append", dest="sources", help="Source name or comma-separated names.")
    parser.add_argument("--dry-run", action="store_true", help="Write a manifest without calling adapters.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    state_dir: Path = args.state_dir.expanduser()
    ensure_state_dirs(state_dir)

    lock_path = state_dir / "plutus-wire.lock"
    with lock_path.open("w", encoding="utf-8") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("plutus-wire: another tick is already running")
            return 0

        sources = normalize_sources(args.sources)
        manifest = build_manifest(state_dir, sources, args.dry_run)
        run_path = state_dir / "runs" / f"{manifest['run_id']}.manifest.json"
        write_json(run_path, manifest)
        print(f"plutus-wire: wrote {run_path}")
        if not args.dry_run:
            print("plutus-wire: adapter execution is intentionally not implemented in M0")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
