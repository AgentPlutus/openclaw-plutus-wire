"""SQLite local store for Plutus Wire raw ingest."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def db_path(state_dir: Path) -> Path:
    return state_dir / "db" / "plutus_wire.sqlite"


def connect_db(state_dir: Path) -> sqlite3.Connection:
    path = db_path(state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            started_at TEXT NOT NULL,
            dry_run INTEGER NOT NULL,
            source_config_hash TEXT,
            manifest_path TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS raw_artifacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            source TEXT NOT NULL,
            path TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL,
            returncode INTEGER,
            post_count INTEGER NOT NULL DEFAULT 0,
            ingested_at TEXT,
            error TEXT,
            FOREIGN KEY(run_id) REFERENCES runs(run_id)
        );

        CREATE TABLE IF NOT EXISTS posts (
            post_id TEXT PRIMARY KEY,
            author TEXT,
            posted_at TEXT,
            text TEXT,
            url TEXT,
            lang TEXT,
            likes INTEGER,
            retweets INTEGER,
            replies INTEGER,
            views INTEGER,
            reply_count INTEGER,
            quote_count INTEGER,
            bookmark_count INTEGER,
            thread_depth INTEGER,
            is_quote_of TEXT,
            original_author TEXT,
            quoted_author TEXT,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            raw_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sightings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            source TEXT NOT NULL,
            post_id TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            source_rank INTEGER NOT NULL,
            raw_json TEXT NOT NULL,
            UNIQUE(run_id, source, post_id),
            FOREIGN KEY(run_id) REFERENCES runs(run_id),
            FOREIGN KEY(post_id) REFERENCES posts(post_id)
        );

        CREATE TABLE IF NOT EXISTS retweet_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            source TEXT NOT NULL,
            retweeter_handle TEXT,
            original_post_id TEXT,
            retweeted_at TEXT,
            observed_at TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(run_id)
        );

        CREATE TABLE IF NOT EXISTS checkpoints (
            source TEXT PRIMARY KEY,
            last_run_id TEXT NOT NULL,
            last_success_at TEXT NOT NULL,
            last_posted_at TEXT,
            newest_post_id TEXT,
            post_count INTEGER NOT NULL,
            artifact_path TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_posts_posted_at ON posts(posted_at);
        CREATE INDEX IF NOT EXISTS idx_sightings_source_observed ON sightings(source, observed_at);
        CREATE INDEX IF NOT EXISTS idx_sightings_post_id ON sightings(post_id);
        """
    )
    conn.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
        ("schema_version", str(SCHEMA_VERSION)),
    )
    conn.commit()


def record_run(conn: sqlite3.Connection, manifest: dict[str, Any], manifest_path: Path) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO runs(run_id, started_at, dry_run, source_config_hash, manifest_path, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            manifest["run_id"],
            manifest.get("started_at") or utc_now(),
            1 if manifest.get("dry_run") else 0,
            manifest.get("source_config_hash"),
            str(manifest_path),
            utc_now(),
        ),
    )
    conn.commit()


def store_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    def count(table: str) -> int:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

    checkpoints = [
        dict(row)
        for row in conn.execute(
            """
            SELECT source, last_run_id, last_success_at, last_posted_at,
                   newest_post_id, post_count, artifact_path
            FROM checkpoints
            ORDER BY source
            """
        )
    ]
    return {
        "schema_version": conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0],
        "counts": {
            "runs": count("runs"),
            "raw_artifacts": count("raw_artifacts"),
            "posts": count("posts"),
            "sightings": count("sightings"),
            "retweet_events": count("retweet_events"),
            "checkpoints": count("checkpoints"),
        },
        "checkpoints": checkpoints,
    }


def ingest_raw_artifact(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    source: str,
    path: Path,
    status: str,
    returncode: int | None,
) -> dict[str, Any]:
    if status != "ok" or returncode not in (0, None):
        return record_artifact(conn, run_id, source, path, status, returncode, 0, "not_ingested")

    try:
        envelopes = parse_opencli_output(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return record_artifact(conn, run_id, source, path, "ingest_error", returncode, 0, str(exc))

    observed_at = utc_now()
    posts_seen = 0
    newest_posted_at: str | None = None
    newest_post_id: str | None = None

    with conn:
        for envelope in envelopes:
            envelope_source = str(envelope.get("source") or envelope.get("feed_type") or source)
            posts = envelope.get("posts") or []
            for idx, post in enumerate(posts):
                post_id = str(post.get("post_id") or "")
                if not post_id:
                    continue
                upsert_post(conn, post, observed_at)
                conn.execute(
                    """
                    INSERT OR IGNORE INTO sightings(run_id, source, post_id, observed_at, source_rank, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (run_id, envelope_source, post_id, observed_at, idx, dump_json(post)),
                )
                posts_seen += 1
                posted_at = post.get("posted_at") or ""
                if posted_at and (newest_posted_at is None or posted_at > newest_posted_at):
                    newest_posted_at = posted_at
                    newest_post_id = post_id
            for event in envelope.get("retweet_events") or []:
                conn.execute(
                    """
                    INSERT INTO retweet_events(
                        run_id, source, retweeter_handle, original_post_id, retweeted_at, observed_at, raw_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        envelope_source,
                        event.get("retweeter_handle"),
                        event.get("original_post_id"),
                        event.get("retweeted_at"),
                        observed_at,
                        dump_json(event),
                    ),
                )

        conn.execute(
            """
            INSERT OR REPLACE INTO raw_artifacts(
                run_id, source, path, status, returncode, post_count, ingested_at, error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, source, str(path), "ingested", returncode, posts_seen, observed_at, None),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO checkpoints(
                source, last_run_id, last_success_at, last_posted_at, newest_post_id,
                post_count, artifact_path, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (source, run_id, observed_at, newest_posted_at, newest_post_id, posts_seen, str(path), observed_at),
        )

    return {
        "status": "ingested",
        "post_count": posts_seen,
        "checkpoint": {
            "source": source,
            "last_success_at": observed_at,
            "last_posted_at": newest_posted_at,
            "newest_post_id": newest_post_id,
        },
    }


def record_artifact(
    conn: sqlite3.Connection,
    run_id: str,
    source: str,
    path: Path,
    status: str,
    returncode: int | None,
    post_count: int,
    error: str | None,
) -> dict[str, Any]:
    with conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO raw_artifacts(
                run_id, source, path, status, returncode, post_count, ingested_at, error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, source, str(path), status, returncode, post_count, utc_now(), error),
        )
    return {"status": status, "post_count": post_count, "error": error}


def upsert_post(conn: sqlite3.Connection, post: dict[str, Any], observed_at: str) -> None:
    raw = dump_json(post)
    post_id = str(post.get("post_id"))
    values = (
        post_id,
        post.get("author"),
        post.get("posted_at"),
        post.get("text"),
        post.get("url"),
        post.get("lang"),
        as_int(post.get("likes")),
        as_int(post.get("retweets")),
        as_int(post.get("replies")),
        as_int(post.get("views")),
        as_int(post.get("reply_count")),
        as_int(post.get("quote_count")),
        as_int(post.get("bookmark_count")),
        as_int(post.get("thread_depth")),
        post.get("is_quote_of"),
        post.get("original_author"),
        post.get("quoted_author"),
        observed_at,
        observed_at,
        raw,
    )
    conn.execute(
        """
        INSERT INTO posts(
            post_id, author, posted_at, text, url, lang, likes, retweets, replies, views,
            reply_count, quote_count, bookmark_count, thread_depth, is_quote_of,
            original_author, quoted_author, first_seen_at, last_seen_at, raw_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(post_id) DO UPDATE SET
            author = excluded.author,
            posted_at = excluded.posted_at,
            text = excluded.text,
            url = excluded.url,
            lang = excluded.lang,
            likes = excluded.likes,
            retweets = excluded.retweets,
            replies = excluded.replies,
            views = excluded.views,
            reply_count = excluded.reply_count,
            quote_count = excluded.quote_count,
            bookmark_count = excluded.bookmark_count,
            thread_depth = excluded.thread_depth,
            is_quote_of = excluded.is_quote_of,
            original_author = excluded.original_author,
            quoted_author = excluded.quoted_author,
            last_seen_at = excluded.last_seen_at,
            raw_json = excluded.raw_json
        """,
        values,
    )


def parse_opencli_output(text: str) -> list[dict[str, Any]]:
    cleaned = text.strip()
    if not cleaned:
        return []
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start == -1 or end == -1 or end < start:
            raise
        payload = json.loads(cleaned[start : end + 1])
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        raise ValueError("OpenCLI output must be a JSON array or object")
    return [item for item in payload if isinstance(item, dict)]


def dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
