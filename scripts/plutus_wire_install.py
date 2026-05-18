#!/usr/bin/env python3
"""One-command local installer for Plutus Wire."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from install_opencli_adapters import SOURCE_DIR, TARGET_DIR, install as install_opencli_adapters
from lib.config import (
    apply_home_tabs,
    apply_source_overrides,
    load_config,
    save_config,
    write_review_config,
)
from lib.store import DEFAULT_STATE_DIR, ensure_state_dirs
from plutus_wire_setup import detect_home_tabs


REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install and initialize Plutus Wire locally.")
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    parser.add_argument(
        "--adapter-mode",
        choices=("copy", "symlink"),
        default="copy",
        help="OpenCLI adapter install strategy. copy is safest for users.",
    )
    parser.add_argument(
        "--no-refresh-adapters",
        action="store_true",
        help="Do not replace an existing ~/.opencli/clis/plutus-wire adapter install.",
    )
    parser.add_argument("--skip-home-tabs", action="store_true", help="Skip X home tab detection.")
    parser.add_argument("--skip-validate", action="store_true", help="Skip opencli validate plutus-wire.")
    parser.add_argument("--enable", action="append", help="Enable source name or comma-separated names.")
    parser.add_argument("--disable", action="append", help="Disable source name or comma-separated names.")
    parser.add_argument("--likes-handle", help="X handle to use when likes is enabled.")
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Run one local ingest and processor smoke after install.",
    )
    parser.add_argument("--limit", type=int, default=20, help="Per-source limit for --run-now.")
    parser.add_argument(
        "--strict-home-tabs",
        action="store_true",
        help="Fail install if home tab detection fails.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    state_dir = args.state_dir.expanduser()
    ensure_state_dirs(state_dir)

    require_command("opencli", "Install OpenCLI first: npm install -g @jackwener/opencli")
    if shutil.which("openclaw") is None:
        print("warning: openclaw not found; local ingest still works, cron install will need OpenClaw later", flush=True)

    refresh_adapters(args.adapter_mode, force=not args.no_refresh_adapters)
    if not args.skip_validate:
        run(["opencli", "validate", "plutus-wire"])

    config = load_config(state_dir)
    if not args.skip_home_tabs:
        try:
            tabs = detect_home_tabs()
        except Exception as exc:
            message = f"home tab detection failed: {exc}"
            if args.strict_home_tabs:
                raise SystemExit(message) from exc
            print(f"warning: {message}", flush=True)
            tabs = []
        if tabs:
            config = apply_home_tabs(config, tabs)
            print(f"detected {len(tabs)} home tab(s)", flush=True)

    config = apply_source_overrides(
        config,
        enable=args.enable,
        disable=args.disable,
        likes_handle=args.likes_handle,
    )
    config_path = save_config(state_dir, config)
    review_config_path = write_review_config(state_dir, config)
    print(f"wrote {config_path}", flush=True)
    print(f"wrote {review_config_path}", flush=True)

    run([sys.executable, str(REPO_ROOT / "scripts" / "plutus_wire_tick.py"), "--state-dir", str(state_dir), "--dry-run"])
    if args.run_now:
        run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "plutus_wire_tick.py"),
                "--state-dir",
                str(state_dir),
                "--execute-adapters",
                "--process",
                "--limit",
                str(args.limit),
            ]
        )

    print("", flush=True)
    print("Plutus Wire local install is ready.", flush=True)
    print("Next commands:", flush=True)
    print(f"  python3 scripts/plutus_wire_db_status.py --state-dir {state_dir}", flush=True)
    print(f"  python3 scripts/serve_review.py --state-dir {state_dir}", flush=True)
    return 0


def refresh_adapters(mode: str, *, force: bool) -> None:
    print(f"installing OpenCLI adapters from {SOURCE_DIR}", flush=True)
    print(f"target: {TARGET_DIR}", flush=True)
    install_opencli_adapters(mode=mode, force=force)
    print("installed OpenCLI adapters", flush=True)


def require_command(name: str, install_hint: str) -> None:
    if shutil.which(name) is None:
        raise SystemExit(f"{name} not found. {install_hint}")


def run(command: list[str], *, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(command), flush=True)
    completed = subprocess.run(command, cwd=cwd, check=False, text=True)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)
    return completed


if __name__ == "__main__":
    raise SystemExit(main())
