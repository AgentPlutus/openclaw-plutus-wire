"""Local state helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_STATE_DIR = Path.home() / ".openclaw" / "state" / "plutus-wire"


def ensure_state_dirs(state_dir: Path) -> None:
    for name in ("runs", "raw", "db", "review", "cloud"):
        (state_dir / name).mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return {} if default is None else dict(default)
    return json.loads(path.read_text(encoding="utf-8"))
