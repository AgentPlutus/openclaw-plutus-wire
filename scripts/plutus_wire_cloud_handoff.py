#!/usr/bin/env python3
"""Build and optionally upload a Plutus Wire cloud handoff package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lib.cloud_handoff import (
    build_cloud_handoff,
    cloud_config_from_dict,
    upload_cloud_package,
    write_cloud_handoff,
)
from lib.config import load_config
from lib.local_store import connect_db, store_summary
from lib.store import DEFAULT_STATE_DIR, ensure_state_dirs, read_json, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Plutus Wire cloud handoff package.")
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    parser.add_argument("--run-manifest", type=Path, help="Run manifest path. Defaults to latest.")
    parser.add_argument("--review-package", type=Path, help="Review package path. Defaults to latest.")
    parser.add_argument("--apply", action="store_true", help="Upload when config allows it.")
    parser.add_argument("--timeout", type=int, default=30, help="Upload timeout seconds.")
    parser.add_argument("--print", action="store_true", help="Print the cloud manifest JSON.")
    args = parser.parse_args()

    state_dir = args.state_dir.expanduser()
    ensure_state_dirs(state_dir)
    config = load_config(state_dir)
    cloud_config = cloud_config_from_dict(config)
    run_manifest = read_json((args.run_manifest or latest_run_manifest(state_dir)).expanduser())
    review_package = read_json((args.review_package or latest_review_package(state_dir)).expanduser())
    conn = connect_db(state_dir)
    try:
        db_summary = store_summary(conn)
    finally:
        conn.close()

    handoff = build_cloud_handoff(
        config=cloud_config,
        run_manifest=run_manifest,
        review_package=review_package,
        db_summary=db_summary,
    )
    paths = write_cloud_handoff(state_dir, handoff)
    manifest = handoff["manifest"]
    print(f"plutus-wire: wrote {paths['latest_manifest_path']}")
    print(f"plutus-wire: wrote {paths['latest_package_path']}")

    if manifest["upload_allowed"] and args.apply:
        result = upload_cloud_package(
            endpoint=cloud_config.endpoint or "",
            manifest_id=manifest["manifest_id"],
            package=handoff["package"],
            timeout=args.timeout,
        )
        manifest["upload_status"] = "uploaded" if result.get("ok") else "upload_error"
        manifest["upload_result"] = result
        write_json(paths["manifest_path"], manifest)
        write_json(paths["latest_manifest_path"], manifest)
        if result.get("ok"):
            print(f"plutus-wire: uploaded manifest {manifest['manifest_id']}")
        else:
            print(f"plutus-wire: upload failed for manifest {manifest['manifest_id']}")
    elif manifest["upload_allowed"]:
        print("plutus-wire: dry-run cloud handoff; pass --apply to upload")
    else:
        print("plutus-wire: cloud handoff disabled")

    if args.print:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


def latest_run_manifest(state_dir: Path) -> Path:
    manifests = sorted((state_dir / "runs").glob("*.manifest.json"))
    if not manifests:
        raise FileNotFoundError("no run manifest found")
    return manifests[-1]


def latest_review_package(state_dir: Path) -> Path:
    path = state_dir / "review" / "latest-package.json"
    if not path.exists():
        raise FileNotFoundError("no review package found; run scripts/plutus_wire_process.py first")
    return path


if __name__ == "__main__":
    raise SystemExit(main())
