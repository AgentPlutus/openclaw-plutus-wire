import pytest

from lib.cloud_handoff import CloudHandoffConfig, build_cloud_handoff, build_cloud_manifest


def test_cloud_sync_is_off_by_default():
    manifest = build_cloud_manifest(
        config=CloudHandoffConfig(),
        run_manifest={"run_id": "r1", "token": "secret"},
    )
    assert manifest["upload_allowed"] is False
    assert manifest["run_manifest"]["token"] == "[redacted]"


def test_enabled_cloud_sync_requires_endpoint():
    with pytest.raises(ValueError):
        build_cloud_manifest(
            config=CloudHandoffConfig(enabled=True, mode="redacted-daily"),
            run_manifest={"run_id": "r1"},
        )


def test_redacted_daily_manifest_allows_upload_after_validation():
    manifest = build_cloud_manifest(
        config=CloudHandoffConfig(
            enabled=True,
            mode="redacted-daily",
            endpoint="https://example.invalid/ingest",
        ),
        run_manifest={"run_id": "r1", "cookie": "do-not-ship"},
        package_summary={"source_count": 2},
    )
    assert manifest["upload_allowed"] is True
    assert manifest["run_manifest"]["cookie"] == "[redacted]"


def test_redacted_daily_package_removes_evidence_text_and_paths():
    handoff = build_cloud_handoff(
        config=CloudHandoffConfig(
            enabled=True,
            mode="redacted-daily",
            endpoint="https://example.invalid/ingest",
        ),
        run_manifest={"run_id": "r1", "raw_path": "/Users/example/raw.json"},
        review_package={
            "run_id": "r1",
            "card_count": 1,
            "cards": [
                {
                    "title": "derived title can remain",
                    "summary": "derived summary can remain",
                    "evidence": [{"text": "raw post text", "url": "https://x.com/a/status/1"}],
                }
            ],
        },
        db_summary={"counts": {"posts": 1}},
    )
    assert handoff["manifest"]["upload_allowed"] is True
    assert handoff["package"]["run_manifest"]["raw_path"] == "[local-path]"
    assert handoff["package"]["review_package"]["cards"][0]["evidence"][0]["text"] == "[redacted-text]"
    assert handoff["package"]["review_package"]["cards"][0]["summary"] == "derived summary can remain"


def test_full_visible_feed_requires_explicit_confirmation():
    with pytest.raises(ValueError):
        build_cloud_handoff(
            config=CloudHandoffConfig(
                enabled=True,
                mode="full-visible-feed",
                endpoint="https://example.invalid/ingest",
            ),
            run_manifest={"run_id": "r1"},
            review_package={"run_id": "r1", "card_count": 0, "cards": []},
            db_summary={"counts": {}},
        )


def test_full_visible_feed_keeps_text_after_confirmation():
    handoff = build_cloud_handoff(
        config=CloudHandoffConfig(
            enabled=True,
            mode="full-visible-feed",
            endpoint="https://example.invalid/ingest",
            allow_full_visible_feed=True,
        ),
        run_manifest={"run_id": "r1"},
        review_package={
            "run_id": "r1",
            "card_count": 1,
            "cards": [{"evidence": [{"text": "visible public post"}]}],
        },
        db_summary={"counts": {}},
    )
    assert handoff["package"]["review_package"]["cards"][0]["evidence"][0]["text"] == "visible public post"
