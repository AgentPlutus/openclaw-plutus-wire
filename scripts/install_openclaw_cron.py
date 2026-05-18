#!/usr/bin/env python3
"""Print or install the planned OpenClaw cron job."""

from __future__ import annotations

import argparse
import shlex
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def build_command(
    every: str,
    *,
    disabled: bool = False,
    include_cloud_handoff: bool = False,
    cloud_apply: bool = False,
) -> list[str]:
    tick_args = ["--execute-adapters", "--process"]
    if include_cloud_handoff:
        tick_args.append("--cloud-handoff")
    if cloud_apply:
        tick_args.append("--cloud-apply")
    message = (
        "Run one Plutus Wire local ingest tick. Execute exactly: "
        f"cd {shlex.quote(str(REPO_ROOT))} && "
        f"python3 scripts/plutus_wire_tick.py {' '.join(tick_args)}. "
        "This performs health preflight, source-local backoff, raw artifact ingest, "
        "SQLite checkpoint updates, and local review card processing. "
        "Cloud handoff may run only when explicitly included and enabled in config. "
        "If it fails, report the failing stage and last relevant lines only. "
        "Never print secrets, cookies, tokens, or local browser credentials."
    )
    command = [
        "openclaw",
        "cron",
        "add",
        "--name",
        "Plutus Wire local ingest",
        "--description",
        "Local-first X timeline intelligence wire. No cloud upload by default.",
        "--every",
        every,
        "--stagger",
        "30s",
        "--session",
        "isolated",
        "--wake",
        "now",
        "--no-deliver",
        "--tools",
        "exec,read,write",
        "--timeout-seconds",
        "1200",
        "--message",
        message,
    ]
    if disabled:
        command.append("--disabled")
    return command


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install Plutus Wire OpenClaw cron.")
    parser.add_argument("--every", default="5m", help="OpenClaw duration, e.g. 5m or 15m.")
    parser.add_argument("--disabled", action="store_true", help="Create the cron job disabled.")
    parser.add_argument("--include-cloud-handoff", action="store_true", help="Include local cloud handoff packaging.")
    parser.add_argument("--cloud-apply", action="store_true", help="Allow upload from cron when config allows it.")
    parser.add_argument("--apply", action="store_true", help="Actually run openclaw cron add.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    command = build_command(
        args.every,
        disabled=args.disabled,
        include_cloud_handoff=args.include_cloud_handoff or args.cloud_apply,
        cloud_apply=args.cloud_apply,
    )
    print(" ".join(shlex.quote(part) for part in command))
    if not args.apply:
        print("dry-run: pass --apply to install this OpenClaw cron job")
        return 0
    completed = subprocess.run(command, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
