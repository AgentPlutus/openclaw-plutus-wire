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
from lib.local_store import (
    connect_db,
    ingest_raw_artifact,
    is_backoff_active,
    parse_opencli_output,
    record_run,
    record_source_failure,
    record_source_success,
)
from lib.opencli_call import find_opencli, opencli_version, run_opencli_capture, run_opencli_json
from lib.cloud_handoff import (
    build_cloud_handoff,
    cloud_config_from_dict,
    upload_cloud_package,
    write_cloud_handoff,
)
from lib.processor import build_review_package, write_review_package
from lib.runtime_status import SKIPPED_BACKOFF, classify_failure, classify_health
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
    parser.add_argument("--skip-health", action="store_true", help="Skip OpenCLI health preflight.")
    parser.add_argument("--health-timeout", type=int, default=90, help="Seconds for OpenCLI health preflight.")
    parser.add_argument("--process", action="store_true", help="Build local review cards after ingest.")
    parser.add_argument("--process-limit", type=int, default=120, help="Maximum input posts for processor.")
    parser.add_argument("--cloud-handoff", action="store_true", help="Build opt-in cloud handoff package.")
    parser.add_argument("--cloud-apply", action="store_true", help="Upload cloud handoff when config allows it.")
    return parser.parse_args()


def run_health_preflight(raw_dir: Path, timeout: int) -> dict[str, Any]:
    output_path = raw_dir / "_health.json"
    stderr_path = output_path.with_suffix(output_path.suffix + ".stderr")
    try:
        completed = run_opencli_capture(["plutus-wire", "health", "--format", "json"], timeout=timeout)
    except Exception as exc:
        classification = classify_failure(str(exc))
        return {
            "status": classification.status,
            "reason": classification.reason,
            "error": str(exc),
        }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(completed.stdout, encoding="utf-8")
    if completed.stderr:
        stderr_path.write_text(completed.stderr, encoding="utf-8")

    payload = None
    if completed.returncode == 0:
        parsed = parse_opencli_output(completed.stdout)
        payload = parsed[0] if parsed else {}
    classification = classify_health(payload, returncode=completed.returncode, stderr=completed.stderr)
    return {
        "status": classification.status,
        "reason": classification.reason,
        "returncode": completed.returncode,
        "raw_path": str(output_path),
        "stderr_path": str(stderr_path) if completed.stderr else None,
        "payload": payload,
    }


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
            if not args.skip_health:
                preflight = run_health_preflight(raw_dir, args.health_timeout)
                manifest["preflight"] = preflight
                if preflight["status"] != "ok":
                    for source_entry in manifest["sources"]:
                        source_entry["status"] = preflight["status"]
                        source_entry["skipped_by_preflight"] = True
                        source_entry["reason"] = preflight.get("reason")
                        if conn is not None:
                            source_entry["runtime"] = record_source_failure(
                                conn,
                                source=source_entry["name"],
                                run_id=manifest["run_id"],
                                state=preflight["status"],
                                error=preflight.get("reason") or preflight.get("error") or "",
                            )
                    write_json(run_path, manifest)
                    if conn is not None:
                        record_run(conn, manifest, run_path)
                        conn.close()
                    print(f"plutus-wire: wrote {run_path}")
                    print(f"plutus-wire: preflight degraded ({preflight['status']})")
                    return 0
            for source_entry in manifest["sources"]:
                name = source_entry["name"]
                if conn is not None:
                    runtime = is_backoff_active(conn, name)
                    if runtime:
                        source_entry["status"] = SKIPPED_BACKOFF
                        source_entry["backoff_until"] = runtime.get("backoff_until")
                        source_entry["reason"] = runtime.get("last_error")
                        continue
                output_path = raw_dir / f"{name}.json"
                try:
                    rc = run_opencli_json(source_entry["opencli_args"], output_path=output_path)
                except Exception as exc:
                    classification = classify_failure(str(exc))
                    source_entry["status"] = classification.status
                    source_entry["error"] = str(exc)
                    if conn is not None:
                        source_entry["runtime"] = record_source_failure(
                            conn,
                            source=name,
                            run_id=manifest["run_id"],
                            state=classification.status,
                            error=str(exc),
                        )
                    continue
                source_entry["raw_path"] = str(output_path)
                source_entry["status"] = "ok" if rc == 0 else "adapter_error"
                source_entry["returncode"] = rc
                if rc != 0:
                    stderr_path = output_path.with_suffix(output_path.suffix + ".stderr")
                    message = read_text_if_exists(stderr_path) or read_text_if_exists(output_path)
                    classification = classify_failure(message, returncode=rc)
                    source_entry["status"] = classification.status
                    source_entry["reason"] = classification.reason
                    if conn is not None:
                        source_entry["runtime"] = record_source_failure(
                            conn,
                            source=name,
                            run_id=manifest["run_id"],
                            state=classification.status,
                            error=message[:1000],
                        )
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
                    if ingest_result["status"] == "ingested":
                        record_source_success(conn, name, manifest["run_id"])
                    elif rc == 0:
                        source_entry["runtime"] = record_source_failure(
                            conn,
                            source=name,
                            run_id=manifest["run_id"],
                            state="adapter_error",
                            error=ingest_result.get("error") or "ingest failed",
                        )
            if args.process:
                if conn is None:
                    manifest["review"] = {"status": "skipped", "reason": "--no-ingest-db"}
                else:
                    review_package = build_review_package(
                        conn,
                        run_id=manifest["run_id"],
                        limit=args.process_limit,
                    )
                    review_paths = write_review_package(state_dir, review_package)
                    manifest["review"] = {
                        "status": "ok",
                        "card_count": review_package["card_count"],
                        "latest_package_path": str(review_paths["latest_package_path"]),
                        "latest_cards_path": str(review_paths["latest_cards_path"]),
                    }
                    if args.cloud_handoff:
                        try:
                            add_cloud_handoff(
                                state_dir=state_dir,
                                config=config,
                                manifest=manifest,
                                review_package=review_package,
                                conn=conn,
                                apply=args.cloud_apply,
                            )
                        except Exception as exc:
                            manifest["cloud_handoff"] = {
                                "status": "error",
                                "error": str(exc)[:1000],
                            }
            elif args.cloud_handoff:
                manifest["cloud_handoff"] = {
                    "status": "skipped",
                    "reason": "--cloud-handoff requires --process in tick",
                }
        elif not args.dry_run:
            manifest["note"] = "adapter execution requires --execute-adapters"
        write_json(run_path, manifest)
        if conn is not None:
            record_run(conn, manifest, run_path)
            conn.close()
        print(f"plutus-wire: wrote {run_path}")
        if not args.execute_adapters:
            print("plutus-wire: adapter execution skipped")
        return 0


def read_text_if_exists(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def add_cloud_handoff(
    *,
    state_dir: Path,
    config: dict[str, Any],
    manifest: dict[str, Any],
    review_package: dict[str, Any],
    conn,
    apply: bool,
) -> None:
    from lib.local_store import store_summary

    cloud_config = cloud_config_from_dict(config)
    handoff = build_cloud_handoff(
        config=cloud_config,
        run_manifest=manifest,
        review_package=review_package,
        db_summary=store_summary(conn),
    )
    paths = write_cloud_handoff(state_dir, handoff)
    cloud_manifest = handoff["manifest"]
    manifest["cloud_handoff"] = {
        "status": cloud_manifest["upload_status"],
        "manifest_id": cloud_manifest["manifest_id"],
        "mode": cloud_manifest["mode"],
        "upload_allowed": cloud_manifest["upload_allowed"],
        "latest_manifest_path": str(paths["latest_manifest_path"]),
        "latest_package_path": str(paths["latest_package_path"]),
    }
    if cloud_manifest["upload_allowed"] and apply:
        result = upload_cloud_package(
            endpoint=cloud_config.endpoint or "",
            manifest_id=cloud_manifest["manifest_id"],
            package=handoff["package"],
        )
        cloud_manifest["upload_status"] = "uploaded" if result.get("ok") else "upload_error"
        cloud_manifest["upload_result"] = result
        write_json(paths["manifest_path"], cloud_manifest)
        write_json(paths["latest_manifest_path"], cloud_manifest)
        manifest["cloud_handoff"]["status"] = cloud_manifest["upload_status"]
        manifest["cloud_handoff"]["upload_result"] = result


if __name__ == "__main__":
    raise SystemExit(main())
