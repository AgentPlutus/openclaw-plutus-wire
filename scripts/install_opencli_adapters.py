#!/usr/bin/env python3
"""Install Plutus Wire OpenCLI adapters into ~/.opencli/clis/plutus-wire."""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = REPO_ROOT / "opencli-clis" / "plutus-wire"
TARGET_DIR = Path.home() / ".opencli" / "clis" / "plutus-wire"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install Plutus Wire OpenCLI adapters.")
    parser.add_argument("--apply", action="store_true", help="Actually install adapters.")
    parser.add_argument("--force", action="store_true", help="Replace an existing target.")
    parser.add_argument(
        "--mode",
        choices=("symlink", "copy"),
        default="copy",
        help="Install strategy. copy is safest for OpenCLI package resolution.",
    )
    return parser.parse_args()


def install(mode: str, force: bool) -> None:
    if not SOURCE_DIR.exists():
        raise SystemExit(f"missing source adapters: {SOURCE_DIR}")
    if TARGET_DIR.exists() or TARGET_DIR.is_symlink():
        if not force:
            raise SystemExit(f"target exists: {TARGET_DIR}; pass --force to replace it")
        if TARGET_DIR.is_symlink() or TARGET_DIR.is_file():
            TARGET_DIR.unlink()
        else:
            shutil.rmtree(TARGET_DIR)
    TARGET_DIR.parent.mkdir(parents=True, exist_ok=True)
    if mode == "symlink":
        os.symlink(SOURCE_DIR, TARGET_DIR, target_is_directory=True)
    else:
        shutil.copytree(SOURCE_DIR, TARGET_DIR)


def main() -> int:
    args = parse_args()
    print(f"source: {SOURCE_DIR}")
    print(f"target: {TARGET_DIR}")
    print(f"mode: {args.mode}")
    if not args.apply:
        print("dry-run: pass --apply to install adapters")
        return 0
    install(args.mode, args.force)
    print("installed. validate with: opencli validate plutus-wire")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
