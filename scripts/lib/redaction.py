"""Redaction helpers for future cloud handoff."""

from __future__ import annotations

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


def redact_for_manifest(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if key.lower() in SECRET_KEYS:
                redacted[key] = "[redacted]"
            else:
                redacted[key] = redact_for_manifest(item)
        return redacted
    if isinstance(value, list):
        return [redact_for_manifest(item) for item in value]
    return value
