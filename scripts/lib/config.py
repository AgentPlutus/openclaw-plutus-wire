"""Plutus Wire source configuration."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .source_registry import SOURCES, default_source_names, source_by_name
from .store import read_json, write_json


CONFIG_VERSION = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_config() -> dict[str, Any]:
    sources: dict[str, Any] = {}
    for source in SOURCES:
        if source.detect_only:
            continue
        sources[source.name] = {
            "enabled": source.default_enabled,
            "label": source.label,
            "default_enabled": source.default_enabled,
            "detected": source.name in {"following", "for-you", "bookmarks", "likes"},
            "support": "supported",
            "requires_handle": source.requires_handle,
            "handle": None,
            "notes": source.notes,
        }
    return {
        "version": CONFIG_VERSION,
        "updated_at": utc_now(),
        "sources": sources,
        "home_tabs": [],
        "cloud_sync": {
            "enabled": False,
            "mode": "off",
            "endpoint": None,
            "allow_full_visible_feed": False,
        },
    }


def config_path(state_dir: Path) -> Path:
    return state_dir / "config.json"


def load_config(state_dir: Path) -> dict[str, Any]:
    path = config_path(state_dir)
    if not path.exists():
        return default_config()
    config = read_json(path)
    return merge_with_defaults(config)


def merge_with_defaults(config: dict[str, Any]) -> dict[str, Any]:
    merged = default_config()
    merged.update({k: v for k, v in config.items() if k not in {"sources", "cloud_sync"}})
    merged["sources"].update(config.get("sources") or {})
    merged["cloud_sync"].update(config.get("cloud_sync") or {})
    return merged


def apply_home_tabs(config: dict[str, Any], tabs: list[dict[str, Any]]) -> dict[str, Any]:
    config = merge_with_defaults(config)
    config["home_tabs"] = tabs
    for tab in tabs:
        slug = str(tab.get("slug") or "")
        if slug in config["sources"]:
            config["sources"][slug]["detected"] = True
            config["sources"][slug]["support"] = tab.get("support") or config["sources"][slug]["support"]
            config["sources"][slug]["label"] = tab.get("label") or config["sources"][slug]["label"]
        elif tab.get("support") == "supported":
            config["sources"][slug] = {
                "enabled": False,
                "label": tab.get("label") or slug,
                "default_enabled": False,
                "detected": True,
                "support": "supported",
                "requires_handle": False,
                "handle": None,
                "notes": "Detected home tab.",
            }
    config["updated_at"] = utc_now()
    return config


def apply_source_overrides(
    config: dict[str, Any],
    *,
    enable: list[str] | None = None,
    disable: list[str] | None = None,
    likes_handle: str | None = None,
) -> dict[str, Any]:
    config = merge_with_defaults(config)
    for name in _split_names(enable):
        source = source_by_name(name)
        if source.detect_only:
            raise ValueError(f"{name} is detection-only and cannot be enabled")
        config["sources"].setdefault(name, default_config()["sources"][name])
        config["sources"][name]["enabled"] = True
    for name in _split_names(disable):
        source = source_by_name(name)
        if source.detect_only:
            raise ValueError(f"{name} is detection-only and cannot be disabled")
        config["sources"].setdefault(name, default_config()["sources"][name])
        config["sources"][name]["enabled"] = False
    if likes_handle is not None:
        handle = likes_handle.strip().lstrip("@") or None
        config["sources"]["likes"]["handle"] = handle
        if handle:
            config["sources"]["likes"]["detected"] = True
    config["updated_at"] = utc_now()
    validate_config(config)
    return config


def apply_cloud_overrides(
    config: dict[str, Any],
    *,
    enable: bool = False,
    disable: bool = False,
    mode: str | None = None,
    endpoint: str | None = None,
    allow_full_visible_feed: bool | None = None,
) -> dict[str, Any]:
    config = merge_with_defaults(config)
    cloud = config["cloud_sync"]
    if disable:
        cloud["enabled"] = False
        cloud["mode"] = "off"
        cloud["endpoint"] = None
        cloud["allow_full_visible_feed"] = False
    if endpoint is not None:
        cloud["endpoint"] = endpoint.strip() or None
    if mode is not None:
        cloud["mode"] = mode
    if allow_full_visible_feed is not None:
        cloud["allow_full_visible_feed"] = allow_full_visible_feed
    if enable:
        cloud["enabled"] = True
        if cloud.get("mode") == "off":
            cloud["mode"] = "redacted-daily"
    config["updated_at"] = utc_now()
    validate_config(config)
    return config


def enabled_source_names(config: dict[str, Any]) -> list[str]:
    config = merge_with_defaults(config)
    enabled: list[str] = []
    for name in config["sources"]:
        if config["sources"][name].get("enabled"):
            source_by_name(name)
            enabled.append(name)
    return enabled or default_source_names()


def source_handle(config: dict[str, Any], name: str, fallback: str | None = None) -> str | None:
    configured = (config.get("sources") or {}).get(name, {}).get("handle")
    return fallback or configured


def validate_config(config: dict[str, Any]) -> None:
    for name, entry in (config.get("sources") or {}).items():
        source = source_by_name(name)
        if source.detect_only and entry.get("enabled"):
            raise ValueError(f"{name} is detection-only and cannot be enabled")
        if entry.get("enabled") and source.requires_handle and not entry.get("handle"):
            raise ValueError(f"{name} requires a handle before it can be enabled")
    cloud = config.get("cloud_sync") or {}
    mode = cloud.get("mode") or "off"
    if mode not in {"off", "manifest-only", "redacted-daily", "full-visible-feed"}:
        raise ValueError(f"unknown cloud sync mode: {mode}")
    if cloud.get("enabled") and mode == "off":
        raise ValueError("cloud sync cannot be enabled with mode=off")
    if not cloud.get("enabled") and mode != "off":
        raise ValueError("cloud sync mode must be off when disabled")
    if cloud.get("enabled") and not cloud.get("endpoint"):
        raise ValueError("cloud sync endpoint is required when enabled")
    if mode == "full-visible-feed" and not cloud.get("allow_full_visible_feed"):
        raise ValueError("full-visible-feed requires explicit confirmation")


def save_config(state_dir: Path, config: dict[str, Any]) -> Path:
    validate_config(config)
    path = config_path(state_dir)
    write_json(path, config)
    return path


def write_review_config(state_dir: Path, config: dict[str, Any]) -> Path:
    review_path = state_dir / "review" / "config.json"
    write_json(review_path, config)
    return review_path


def source_config_hash(config: dict[str, Any]) -> str:
    payload = json.dumps(config.get("sources", {}), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _split_names(values: list[str] | None) -> list[str]:
    names: list[str] = []
    for value in values or []:
        for part in value.split(","):
            name = part.strip().lower()
            if name and name not in names:
                names.append(name)
    return names
