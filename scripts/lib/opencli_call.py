"""OpenCLI subprocess helpers."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def find_opencli() -> str | None:
    return shutil.which("opencli")


def opencli_version() -> str | None:
    exe = find_opencli()
    if not exe:
        return None
    try:
        completed = subprocess.run(
            [exe, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return None
    output = (completed.stdout or completed.stderr).strip()
    return output or None


def run_opencli_json(args: list[str], *, output_path: Path, timeout: int = 300) -> int:
    exe = find_opencli()
    if not exe:
        raise FileNotFoundError("opencli not found in PATH")
    completed = subprocess.run(
        [exe, *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(completed.stdout, encoding="utf-8")
    if completed.stderr:
        output_path.with_suffix(output_path.suffix + ".stderr").write_text(completed.stderr, encoding="utf-8")
    return completed.returncode
