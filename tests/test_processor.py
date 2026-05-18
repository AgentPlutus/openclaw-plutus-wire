import json

from lib.local_store import connect_db, ingest_raw_artifact, record_run
from lib.processor import build_review_package, write_review_package


def test_processor_builds_review_cards_from_sqlite(tmp_path):
    state_dir = tmp_path / "state"
    conn = connect_db(state_dir)
    manifest = {
        "run_id": "20260518T010000Z",
        "started_at": "2026-05-18T01:00:00Z",
        "dry_run": False,
        "source_config_hash": "abc",
    }
    manifest_path = state_dir / "runs" / "20260518T010000Z.manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    record_run(conn, manifest, manifest_path)

    raw_path = state_dir / "raw" / "20260518T010000Z" / "following.json"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_text(
        json.dumps(
            [
                {
                    "source": "following",
                    "posts": [
                        {
                            "post_id": "p1",
                            "author": "alice",
                            "posted_at": "2026-05-18T01:00:00Z",
                            "text": "Signal about $AI with https://example.com/report",
                            "url": "https://x.com/alice/status/p1",
                            "likes": 100,
                        },
                        {
                            "post_id": "p2",
                            "author": "bob",
                            "posted_at": "2026-05-18T01:01:00Z",
                            "text": "Another angle on https://example.com/report",
                            "url": "https://x.com/bob/status/p2",
                            "likes": 10,
                        },
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )
    ingest_raw_artifact(conn, run_id=manifest["run_id"], source="following", path=raw_path, status="ok", returncode=0)

    package = build_review_package(conn, run_id=manifest["run_id"])
    paths = write_review_package(state_dir, package)

    assert package["card_count"] == 1
    assert package["cards"][0]["post_count"] == 2
    assert package["cards"][0]["anchors"]["external_urls"] == ["https://example.com/report"]
    assert paths["latest_cards_path"].exists()
    conn.close()
