from lib.source_registry import default_source_names, normalize_sources, source_by_name


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
