import pytest

from lib.cloud_handoff import CloudHandoffConfig, build_cloud_manifest


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
