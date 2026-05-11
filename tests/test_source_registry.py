import pytest

from lib.source_registry import (
    default_source_names,
    normalize_sources,
    opencli_args_for_source,
    source_by_name,
)


def test_default_sources_are_following_and_for_you():
    assert default_source_names() == ["following", "for-you"]


def test_optional_ai_is_not_default():
    assert "ai" not in default_source_names()
    assert source_by_name("ai").default_enabled is False


def test_normalize_sources_accepts_commas_and_dedupes():
    assert normalize_sources(["following,ai", "ai", "bookmarks"]) == [
        "following",
        "ai",
        "bookmarks",
    ]


def test_home_tabs_is_detection_only():
    with pytest.raises(ValueError):
        normalize_sources(["home-tabs"])


def test_opencli_args_for_timeline_source():
    assert opencli_args_for_source("following", limit=20) == [
        "plutus-wire",
        "timeline",
        "--type",
        "following",
        "--limit",
        "20",
        "--format",
        "json",
    ]


def test_likes_requires_handle():
    with pytest.raises(ValueError):
        opencli_args_for_source("likes", limit=20)
    assert opencli_args_for_source("likes", limit=20, handle="@example_user") == [
        "plutus-wire",
        "likes",
        "--limit",
        "20",
        "--handle",
        "example_user",
        "--format",
        "json",
    ]
