import json

from lib.local_store import (
    connect_db,
    ingest_raw_artifact,
    parse_opencli_output,
    record_run,
    store_summary,
)


def sample_manifest():
    return {
        "run_id": "20260518T000000Z",
        "started_at": "2026-05-18T00:00:00Z",
        "dry_run": False,
        "source_config_hash": "abc123",
    }


def sample_raw_payload():
    return [
        {
            "source": "following",
            "feed_type": "following",
            "ran_at": "2026-05-18T00:00:01Z",
            "posts": [
                {
                    "post_id": "1",
                    "author": "alice",
                    "posted_at": "2026-05-18T00:00:00Z",
                    "text": "first",
                    "url": "https://x.com/alice/status/1",
                    "likes": 1,
                    "retweets": 2,
                    "replies": 3,
                    "views": 4,
                    "lang": "en",
                },
                {
                    "post_id": "2",
                    "author": "bob",
                    "posted_at": "2026-05-18T00:01:00Z",
                    "text": "second",
                    "url": "https://x.com/bob/status/2",
                    "likes": 5,
                    "retweets": 6,
                    "replies": 7,
                    "views": 8,
                    "lang": "en",
                },
            ],
            "retweet_events": [
                {
                    "retweeter_handle": "carol",
                    "original_post_id": "2",
                    "retweeted_at": None,
                }
            ],
        }
    ]


def test_parse_opencli_output_accepts_noisy_json_array():
    parsed = parse_opencli_output("noise\n" + json.dumps(sample_raw_payload()) + "\nmore")
    assert parsed[0]["posts"][0]["post_id"] == "1"


def test_ingest_raw_artifact_populates_posts_sightings_and_checkpoint(tmp_path):
    state_dir = tmp_path / "state"
    conn = connect_db(state_dir)
    manifest_path = state_dir / "runs" / "20260518T000000Z.manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps(sample_manifest()), encoding="utf-8")
    record_run(conn, sample_manifest(), manifest_path)

    raw_path = state_dir / "raw" / "20260518T000000Z" / "following.json"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_text(json.dumps(sample_raw_payload()), encoding="utf-8")

    result = ingest_raw_artifact(
        conn,
        run_id="20260518T000000Z",
        source="following",
        path=raw_path,
        status="ok",
        returncode=0,
    )
    summary = store_summary(conn)

    assert result["status"] == "ingested"
    assert result["post_count"] == 2
    assert summary["counts"]["posts"] == 2
    assert summary["counts"]["sightings"] == 2
    assert summary["counts"]["retweet_events"] == 1
    assert summary["checkpoints"][0]["source"] == "following"
    assert summary["checkpoints"][0]["newest_post_id"] == "2"
    conn.close()
