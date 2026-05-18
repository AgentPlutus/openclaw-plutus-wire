#!/usr/bin/env python3
"""Run one Plutus Wire ingest tick."""

from __future__ import annotations

import argparse
import fcntl
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.config import (
    enabled_source_names,
    load_config,
    source_config_hash,
    source_handle,
)
from lib.local_store import connect_db, ingest_raw_artifact, record_run
from lib.opencli_call import find_opencli, opencli_version, run_opencli_json
from lib.source_registry import normalize_sources, opencli_args_for_source, source_by_name
from lib.store import DEFAULT_STATE_DIR, ensure_state_dirs, write_json


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_manifest(
    state_dir: Path,
    sources: list[str],
    *,
    config: dict[str, Any],
    dry_run: bool,
    limit: int,
    handle: str | None,
) -> dict[str, Any]:
    return {
        "run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "started_at": utc_now(),
        "dry_run": dry_run,
        "state_dir": str(state_dir),
        "opencli_path": find_opencli(),
        "opencli_version": opencli_version(),
        "adapter_version": "0.1.0a0",
        "source_config_hash": source_config_hash(config),
        "sources": [
            {
                "name": name,
                "label": source_by_name(name).label,
                "adapter_command": source_by_name(name).adapter_command,
                "opencli_args": opencli_args_for_source(
                    name,
                    limit=limit,
                    handle=source_handle(config, name, handle),
                ),
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
    parser.add_argument("--config", type=Path, help="Config file path. Defaults to <state-dir>/config.json.")
    parser.add_argument("--ignore-config", action="store_true", help="Use built-in defaults and CLI sources only.")
    parser.add_argument("--source", action="append", dest="sources", help="Source name or comma-separated names.")
    parser.add_argument("--limit", type=int, default=80, help="Per-source adapter limit.")
    parser.add_argument("--handle", help="X handle for sources that require it, such as likes.")
    parser.add_argument("--dry-run", action="store_true", help="Write a manifest without calling adapters.")
    parser.add_argument("--execute-adapters", action="store_true", help="Call OpenCLI adapters and write raw JSON.")
    parser.add_argument("--no-ingest-db", action="store_true", help="Do not ingest raw adapter output into SQLite.")
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

        config = {} if args.ignore_config else load_config(state_dir)
        if args.config:
            from lib.store import read_json

            config = read_json(args.config.expanduser())
        sources = normalize_sources(args.sources) if args.sources else enabled_source_names(config)
        manifest = build_manifest(
            state_dir,
            sources,
            config=config,
            dry_run=args.dry_run or not args.execute_adapters,
            limit=args.limit,
            handle=args.handle,
        )
        run_path = state_dir / "runs" / f"{manifest['run_id']}.manifest.json"
        raw_dir = state_dir / "raw" / manifest["run_id"]
        write_json(run_path, manifest)
        conn = None if args.no_ingest_db else connect_db(state_dir)
        if conn is not None:
            record_run(conn, manifest, run_path)
        if args.execute_adapters and not args.dry_run:
            for source_entry in manifest["sources"]:
                name = source_entry["name"]
                output_path = raw_dir / f"{name}.json"
                try:
                    rc = run_opencli_json(source_entry["opencli_args"], output_path=output_path)
                except Exception as exc:
                    source_entry["status"] = "adapter_error"
                    source_entry["error"] = str(exc)
                    continue
                source_entry["raw_path"] = str(output_path)
                source_entry["status"] = "ok" if rc == 0 else "adapter_error"
                source_entry["returncode"] = rc
                if conn is not None:
                    ingest_result = ingest_raw_artifact(
                        conn,
                        run_id=manifest["run_id"],
                        source=name,
                        path=output_path,
                        status=source_entry["status"],
                        returncode=rc,
                    )
                    source_entry["ingest_status"] = ingest_result["status"]
                    source_entry["post_count"] = ingest_result.get("post_count", 0)
                    if ingest_result.get("checkpoint"):
                        source_entry["checkpoint"] = ingest_result["checkpoint"]
                    if ingest_result.get("error"):
                        source_entry["ingest_error"] = ingest_result["error"]
        elif not args.dry_run:
            manifest["note"] = "adapter execution requires --execute-adapters in M1"
        write_json(run_path, manifest)
        if conn is not None:
            record_run(conn, manifest, run_path)
            conn.close()
        print(f"plutus-wire: wrote {run_path}")
        if not args.execute_adapters:
            print("plutus-wire: adapter execution skipped")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
