"""Redaction helpers for cloud handoff."""

from __future__ import annotations

import hashlib
import re
from typing import Any


SECRET_KEYS = {
    "cookie",
    "cookies",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "password",
    "secret",
}

PATH_KEYS = {
    "path",
    "raw_path",
    "stderr_path",
    "manifest_path",
    "artifact_path",
    "state_dir",
}

TEXT_KEYS = {
    "text",
}

LOCAL_PATH_RE = re.compile(r"^(~?/|/Users/|/private/|/var/folders/|/tmp/)")


def redact_for_manifest(value: Any) -> Any:
    return redact_for_mode(value, mode="manifest-only")


def redact_for_mode(value: Any, *, mode: str, allow_post_text: bool = False, key: str | None = None) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            lower = key.lower()
            if lower in SECRET_KEYS:
                redacted[key] = "[redacted]"
            elif lower in PATH_KEYS or lower.endswith("_path"):
                redacted[key] = "[local-path]"
            elif lower in TEXT_KEYS and not allow_post_text:
                redacted[key] = "[redacted-text]"
            else:
                redacted[key] = redact_for_mode(item, mode=mode, allow_post_text=allow_post_text, key=key)
        return redacted
    if isinstance(value, list):
        return [redact_for_mode(item, mode=mode, allow_post_text=allow_post_text, key=key) for item in value]
    if isinstance(value, str):
        return redact_string(value, key=key)
    return value


def redact_string(value: str, *, key: str | None = None) -> str:
    if LOCAL_PATH_RE.match(value):
        return "[local-path]"
    if key and key.lower().endswith("_id") and len(value) > 64:
        return hash_value(value)
    return value


def hash_value(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
