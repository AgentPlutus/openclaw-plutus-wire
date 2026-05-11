"""OpenCLI subprocess helpers."""

from __future__ import annotations

import shutil
import subprocess


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
