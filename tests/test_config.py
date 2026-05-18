import pytest

from lib.config import (
    apply_home_tabs,
    apply_cloud_overrides,
    apply_source_overrides,
    default_config,
    enabled_source_names,
    source_config_hash,
    source_handle,
)


def test_default_config_enables_following_and_for_you_only():
    config = default_config()
    assert enabled_source_names(config) == ["following", "for-you"]
    assert config["sources"]["ai"]["enabled"] is False
    assert config["cloud_sync"]["mode"] == "off"


def test_home_tabs_marks_ai_detected_but_not_enabled():
    config = apply_home_tabs(
        default_config(),
        [
            {"slug": "for-you", "label": "For you", "support": "supported"},
            {"slug": "ai", "label": "AI", "support": "supported"},
            {"slug": "business", "label": "Business", "support": "detected_only"},
        ],
    )
    assert config["sources"]["ai"]["detected"] is True
    assert config["sources"]["ai"]["enabled"] is False
    assert "business" not in config["sources"]


def test_enable_likes_requires_handle():
    with pytest.raises(ValueError):
        apply_source_overrides(default_config(), enable=["likes"])


def test_enable_likes_with_handle():
    config = apply_source_overrides(
        default_config(),
        enable=["likes"],
        likes_handle="@example_user",
    )
    assert "likes" in enabled_source_names(config)
    assert source_handle(config, "likes") == "example_user"


def test_source_config_hash_changes_with_sources():
    config = default_config()
    changed = apply_source_overrides(default_config(), enable=["bookmarks"])
    assert source_config_hash(config) != source_config_hash(changed)


def test_cloud_sync_requires_explicit_endpoint():
    with pytest.raises(ValueError):
        apply_cloud_overrides(default_config(), enable=True)


def test_cloud_sync_redacted_daily_config():
    config = apply_cloud_overrides(
        default_config(),
        enable=True,
        mode="redacted-daily",
        endpoint="https://example.invalid/plutus-wire",
    )
    assert config["cloud_sync"]["enabled"] is True
    assert config["cloud_sync"]["mode"] == "redacted-daily"


def test_full_visible_feed_requires_confirmation():
    with pytest.raises(ValueError):
        apply_cloud_overrides(
            default_config(),
            enable=True,
            mode="full-visible-feed",
            endpoint="https://example.invalid/plutus-wire",
        )
