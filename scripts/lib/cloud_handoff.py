"""Cloud handoff manifest helpers.

This module prepares local manifests only. It must not upload data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .redaction import redact_for_manifest


SYNC_MODES = {"off", "manifest-only", "redacted-daily", "full-visible-feed"}


@dataclass(frozen=True)
class CloudHandoffConfig:
    enabled: bool = False
    mode: str = "off"
    endpoint: str | None = None

    def validate(self) -> None:
        if self.mode not in SYNC_MODES:
            raise ValueError(f"unknown cloud sync mode: {self.mode}")
        if not self.enabled and self.mode != "off":
            raise ValueError("cloud sync mode must be off when disabled")
        if self.enabled and not self.endpoint:
            raise ValueError("cloud sync endpoint is required when enabled")


def build_cloud_manifest(
    *,
    config: CloudHandoffConfig,
    run_manifest: dict[str, Any],
    package_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config.validate()
    return {
        "enabled": config.enabled,
        "mode": config.mode,
        "endpoint": config.endpoint if config.enabled else None,
        "run_manifest": redact_for_manifest(run_manifest),
        "package_summary": redact_for_manifest(package_summary or {}),
        "upload_allowed": bool(config.enabled and config.mode != "off"),
    }
