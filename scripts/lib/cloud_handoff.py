"""Cloud handoff manifest, package, and upload helpers."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from .local_store import utc_now
from .redaction import redact_for_manifest, redact_for_mode
from .store import write_json


SYNC_MODES = {"off", "manifest-only", "redacted-daily", "full-visible-feed"}


@dataclass(frozen=True)
class CloudHandoffConfig:
    enabled: bool = False
    mode: str = "off"
    endpoint: str | None = None
    allow_full_visible_feed: bool = False

    def validate(self) -> None:
        if self.mode not in SYNC_MODES:
            raise ValueError(f"unknown cloud sync mode: {self.mode}")
        if not self.enabled and self.mode != "off":
            raise ValueError("cloud sync mode must be off when disabled")
        if self.enabled and self.mode == "off":
            raise ValueError("cloud sync cannot be enabled with mode=off")
        if self.enabled and not self.endpoint:
            raise ValueError("cloud sync endpoint is required when enabled")
        if self.mode == "full-visible-feed" and not self.allow_full_visible_feed:
            raise ValueError("full-visible-feed requires explicit confirmation")


def cloud_config_from_dict(config: dict[str, Any]) -> CloudHandoffConfig:
    cloud = config.get("cloud_sync") or {}
    return CloudHandoffConfig(
        enabled=bool(cloud.get("enabled")),
        mode=str(cloud.get("mode") or "off"),
        endpoint=cloud.get("endpoint"),
        allow_full_visible_feed=bool(cloud.get("allow_full_visible_feed")),
    )


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


def build_cloud_handoff(
    *,
    config: CloudHandoffConfig,
    run_manifest: dict[str, Any],
    review_package: dict[str, Any],
    db_summary: dict[str, Any],
) -> dict[str, Any]:
    config.validate()
    created_at = utc_now()
    run_id = str(run_manifest.get("run_id") or review_package.get("run_id") or "no-run")
    summary = {
        "run_id": run_id,
        "created_at": created_at,
        "mode": config.mode,
        "card_count": int(review_package.get("card_count") or 0),
        "db_counts": db_summary.get("counts") or {},
    }
    package = build_package_payload(
        config=config,
        run_manifest=run_manifest,
        review_package=review_package,
        db_summary=db_summary,
    )
    package_bytes = json.dumps(package, ensure_ascii=False, sort_keys=True).encode("utf-8")
    manifest_id = stable_manifest_id(config.mode, run_id, package_bytes)
    manifest = {
        "schema_version": 1,
        "manifest_id": manifest_id,
        "created_at": created_at,
        "enabled": config.enabled,
        "mode": config.mode,
        "endpoint": config.endpoint if config.enabled else None,
        "run_id": run_id,
        "package_sha256": sha256(package_bytes).hexdigest(),
        "package_bytes": len(package_bytes),
        "summary": summary,
        "upload_allowed": bool(config.enabled and config.mode != "off"),
        "upload_status": "ready" if config.enabled and config.mode != "off" else "disabled",
    }
    return {"manifest": manifest, "package": package}


def build_package_payload(
    *,
    config: CloudHandoffConfig,
    run_manifest: dict[str, Any],
    review_package: dict[str, Any],
    db_summary: dict[str, Any],
) -> dict[str, Any]:
    base = {
        "schema_version": 1,
        "mode": config.mode,
        "run_manifest": redact_for_manifest(run_manifest),
        "db_summary": redact_for_manifest(db_summary),
    }
    if config.mode == "off":
        return base
    if config.mode == "manifest-only":
        base["review_summary"] = {
            "processor_version": review_package.get("processor_version"),
            "created_at": review_package.get("created_at"),
            "run_id": review_package.get("run_id"),
            "card_count": review_package.get("card_count"),
            "stats": review_package.get("stats") or {},
        }
        return base
    if config.mode == "redacted-daily":
        base["review_package"] = redact_for_mode(
            review_package,
            mode=config.mode,
            allow_post_text=False,
        )
        return base
    if config.mode == "full-visible-feed":
        base["review_package"] = redact_for_mode(
            review_package,
            mode=config.mode,
            allow_post_text=True,
        )
        return base
    raise ValueError(f"unknown cloud sync mode: {config.mode}")


def write_cloud_handoff(state_dir: Path, handoff: dict[str, Any]) -> dict[str, Path]:
    manifest = handoff["manifest"]
    package = handoff["package"]
    cloud_dir = state_dir / "cloud"
    manifest_id = manifest["manifest_id"]
    manifest_path = cloud_dir / f"{manifest_id}.manifest.json"
    package_path = cloud_dir / f"{manifest_id}.package.json"
    latest_manifest_path = cloud_dir / "latest-manifest.json"
    latest_package_path = cloud_dir / "latest-package.json"
    write_json(manifest_path, manifest)
    write_json(package_path, package)
    write_json(latest_manifest_path, manifest)
    write_json(latest_package_path, package)
    return {
        "manifest_path": manifest_path,
        "package_path": package_path,
        "latest_manifest_path": latest_manifest_path,
        "latest_package_path": latest_package_path,
    }


def upload_cloud_package(
    *,
    endpoint: str,
    manifest_id: str,
    package: dict[str, Any],
    timeout: int = 30,
) -> dict[str, Any]:
    body = json.dumps(package, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "plutus-wire/0.1",
            "X-Plutus-Wire-Manifest-Id": manifest_id,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return {
                "ok": 200 <= response.status < 300,
                "status": response.status,
                "body": response.read(2048).decode("utf-8", errors="replace"),
            }
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "status": exc.code,
            "body": exc.read(2048).decode("utf-8", errors="replace"),
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": None,
            "error": str(exc),
        }


def stable_manifest_id(mode: str, run_id: str, package_bytes: bytes) -> str:
    digest = sha256(mode.encode("utf-8") + b"\0" + run_id.encode("utf-8") + b"\0" + package_bytes).hexdigest()
    return f"pw-{run_id}-{digest[:12]}"
