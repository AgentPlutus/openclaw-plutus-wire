#!/usr/bin/env python3
"""Configure Plutus Wire sources."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from lib.config import (
    apply_home_tabs,
    apply_source_overrides,
    load_config,
    save_config,
    write_review_config,
)
from lib.store import DEFAULT_STATE_DIR, ensure_state_dirs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Configure Plutus Wire sources.")
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    parser.add_argument("--detect-home-tabs", action="store_true", help="Run opencli plutus-wire home-tabs.")
    parser.add_argument("--home-tabs-file", type=Path, help="Use saved home-tabs JSON instead of calling OpenCLI.")
    parser.add_argument("--enable", action="append", help="Enable source name or comma-separated names.")
    parser.add_argument("--disable", action="append", help="Disable source name or comma-separated names.")
    parser.add_argument("--likes-handle", help="X handle to use when likes is enabled.")
    parser.add_argument("--dry-run", action="store_true", help="Print config without writing it.")
    return parser.parse_args()


def detect_home_tabs() -> list[dict[str, Any]]:
    completed = subprocess.run(
        ["opencli", "plutus-wire", "home-tabs", "--format", "json"],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip() or "home-tabs failed")
    payload = parse_json_array(completed.stdout)
    if not payload:
        return []
    return payload[0].get("tabs") or []


def read_home_tabs_file(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list) and payload and isinstance(payload[0], dict) and "tabs" in payload[0]:
        return payload[0]["tabs"] or []
    if isinstance(payload, list):
        return payload
    raise ValueError(f"unsupported home-tabs file shape: {path}")


def parse_json_array(text: str) -> list[Any]:
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise ValueError("OpenCLI output did not contain a JSON array")
    return json.loads(text[start : end + 1])


def main() -> int:
    args = parse_args()
    state_dir: Path = args.state_dir.expanduser()
    ensure_state_dirs(state_dir)

    config = load_config(state_dir)
    if args.home_tabs_file:
        config = apply_home_tabs(config, read_home_tabs_file(args.home_tabs_file.expanduser()))
    elif args.detect_home_tabs:
        config = apply_home_tabs(config, detect_home_tabs())

    config = apply_source_overrides(
        config,
        enable=args.enable,
        disable=args.disable,
        likes_handle=args.likes_handle,
    )

    if args.dry_run:
        print(json.dumps(config, ensure_ascii=False, indent=2))
        return 0

    config_path = save_config(state_dir, config)
    review_path = write_review_config(state_dir, config)
    print(f"wrote {config_path}")
    print(f"wrote {review_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
