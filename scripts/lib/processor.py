"""Deterministic processor for local review cards."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

from .local_store import utc_now
from .store import write_json


PROCESSOR_VERSION = "processor_v0"
URL_RE = re.compile(r"https?://[^\s)>\"]+")
TAG_RE = re.compile(r"(?<!\w)([#@$][A-Za-z0-9_]{2,40})")


def build_review_package(
    conn,
    *,
    run_id: str | None = None,
    limit: int = 120,
    language: str = "source",
) -> dict[str, Any]:
    rows = fetch_recent_posts(conn, run_id=run_id, limit=limit)
    groups = group_posts(rows)
    cards = [build_card(group) for group in groups]
    cards.sort(key=lambda card: (card["score"], card["last_seen_at"] or ""), reverse=True)
    return {
        "schema_version": 1,
        "processor_version": PROCESSOR_VERSION,
        "created_at": utc_now(),
        "run_id": run_id,
        "language": language,
        "card_count": len(cards),
        "stats": {
            "input_posts": len(rows),
            "group_count": len(groups),
            "source_counts": dict(count_sources(rows)),
        },
        "cards": cards,
    }


def fetch_recent_posts(conn, *, run_id: str | None, limit: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            p.post_id,
            p.author,
            p.posted_at,
            p.text,
            p.url,
            p.lang,
            p.likes,
            p.retweets,
            p.replies,
            p.views,
            p.reply_count,
            p.quote_count,
            p.bookmark_count,
            p.thread_depth,
            p.is_quote_of,
            p.original_author,
            p.quoted_author,
            p.first_seen_at,
            p.last_seen_at,
            p.raw_json,
            GROUP_CONCAT(DISTINCT s.source) AS sources,
            GROUP_CONCAT(DISTINCT s.run_id) AS run_ids,
            COUNT(s.id) AS sighting_count,
            MIN(s.observed_at) AS first_observed_at,
            MAX(s.observed_at) AS last_observed_at
        FROM posts p
        JOIN sightings s ON s.post_id = p.post_id
        WHERE (? IS NULL OR s.run_id = ?)
        GROUP BY p.post_id
        ORDER BY COALESCE(p.posted_at, p.last_seen_at, p.first_seen_at) DESC
        LIMIT ?
        """,
        (run_id, run_id, limit),
    ).fetchall()
    return [normalize_post_row(row) for row in rows]


def normalize_post_row(row) -> dict[str, Any]:
    item = dict(row)
    raw = parse_raw_json(item.get("raw_json"))
    text = item.get("text") or raw.get("text") or ""
    item["text"] = normalize_space(text)
    item["sources"] = split_csv(item.get("sources"))
    item["run_ids"] = split_csv(item.get("run_ids"))
    item["tags"] = extract_tags(text)
    item["external_urls"] = extract_external_urls(text, item.get("url"))
    item["raw"] = raw
    return item


def group_posts(posts: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for post in posts:
        key = group_key(post)
        buckets.setdefault(key, []).append(post)
    return list(buckets.values())


def group_key(post: dict[str, Any]) -> str:
    quoted = post.get("is_quote_of") or post.get("raw", {}).get("is_quote_of")
    if quoted:
        return f"quote:{quoted}"
    if post["external_urls"]:
        return f"url:{post['external_urls'][0]}"
    tags = post.get("tags") or []
    author = (post.get("author") or "").lower()
    if author and len(tags) >= 2:
        return "author-tags:" + author + ":" + ",".join(tags[:4])
    return f"post:{post.get('post_id')}"


def build_card(group: list[dict[str, Any]]) -> dict[str, Any]:
    group = sorted(group, key=lambda post: post.get("posted_at") or "", reverse=True)
    primary = group[0]
    post_ids = [str(post.get("post_id")) for post in group if post.get("post_id")]
    sources = sorted({source for post in group for source in post.get("sources", [])})
    source_counts = Counter(source for post in group for source in post.get("sources", []))
    urls = dedupe([post.get("url") for post in group if post.get("url")])
    external_urls = dedupe([url for post in group for url in post.get("external_urls", [])])
    title = make_title(primary)
    summary = make_summary(group, sources)
    score = score_group(group, sources)
    return {
        "card_id": stable_id(group_key(primary), post_ids),
        "status": "review",
        "group_key": group_key(primary),
        "title": title,
        "summary": summary,
        "why_it_matters": why_it_matters(group, sources),
        "what_to_check": what_to_check(group),
        "source_provenance": [
            {"source": source, "sighting_count": source_counts[source]} for source in sorted(source_counts)
        ],
        "anchors": {
            "post_ids": post_ids,
            "urls": urls,
            "external_urls": external_urls,
            "tags": sorted({tag for post in group for tag in post.get("tags", [])}),
        },
        "evidence": [evidence_item(post) for post in group[:6]],
        "post_count": len(group),
        "score": score,
        "first_seen_at": min((post.get("first_observed_at") or post.get("first_seen_at") or "") for post in group),
        "last_seen_at": max((post.get("last_observed_at") or post.get("last_seen_at") or "") for post in group),
    }


def write_review_package(state_dir: Path, package: dict[str, Any]) -> dict[str, Path]:
    review_dir = state_dir / "review"
    run_id = package.get("run_id") or package["created_at"].replace(":", "").replace("-", "")
    package_path = review_dir / f"{run_id}.review-package.json"
    latest_package_path = review_dir / "latest-package.json"
    latest_cards_path = review_dir / "latest-cards.json"
    write_json(package_path, package)
    write_json(latest_package_path, package)
    write_json(
        latest_cards_path,
        {
            "schema_version": package["schema_version"],
            "processor_version": package["processor_version"],
            "created_at": package["created_at"],
            "run_id": package.get("run_id"),
            "card_count": package["card_count"],
            "cards": package["cards"],
        },
    )
    return {
        "package_path": package_path,
        "latest_package_path": latest_package_path,
        "latest_cards_path": latest_cards_path,
    }


def make_title(post: dict[str, Any]) -> str:
    author = post.get("author") or "unknown"
    text = snippet(post.get("text") or "", 96)
    return f"{author}: {text}" if text else f"{author} posted an item"


def make_summary(group: list[dict[str, Any]], sources: list[str]) -> str:
    primary = group[0]
    text = snippet(primary.get("text") or "", 220)
    source_label = ", ".join(sources) if sources else "unknown source"
    if len(group) == 1:
        return f"Seen in {source_label}: {text}"
    return f"{len(group)} related posts seen in {source_label}. Lead item: {text}"


def why_it_matters(group: list[dict[str, Any]], sources: list[str]) -> str:
    if len(sources) > 1:
        return "The same signal crossed multiple selected sources, so it is worth checking outside one ranking view."
    if max_metric(group, "views") >= 100000 or max_metric(group, "likes") >= 1000:
        return "The item has visible engagement and may be shaping the surrounding conversation."
    if any(post.get("external_urls") for post in group):
        return "The post points outside the timeline and can be checked against the linked source."
    return "Review whether this adds evidence beyond the default timeline ranking."


def what_to_check(group: list[dict[str, Any]]) -> list[str]:
    checks = ["Open the source post before accepting the signal."]
    if any(post.get("external_urls") for post in group):
        checks.append("Read the linked source and compare it with the post summary.")
    if len(group) > 1:
        checks.append("Check whether repeated posts add new evidence or only amplify the same claim.")
    checks.append("Look for a contrary source before promoting it to a brief.")
    return checks


def evidence_item(post: dict[str, Any]) -> dict[str, Any]:
    return {
        "post_id": post.get("post_id"),
        "author": post.get("author"),
        "posted_at": post.get("posted_at"),
        "url": post.get("url"),
        "sources": post.get("sources", []),
        "text": post.get("text"),
        "metrics": {
            "likes": post.get("likes"),
            "retweets": post.get("retweets"),
            "replies": post.get("replies"),
            "views": post.get("views"),
        },
    }


def score_group(group: list[dict[str, Any]], sources: list[str]) -> int:
    engagement = sum(max(0, int(post.get("likes") or 0)) for post in group)
    return len(group) * 10 + len(sources) * 15 + min(100, engagement // 25)


def count_sources(posts: list[dict[str, Any]]) -> Counter:
    counter: Counter = Counter()
    for post in posts:
        counter.update(post.get("sources", []))
    return counter


def extract_tags(text: str) -> list[str]:
    return dedupe(token.lower() for token in TAG_RE.findall(text or ""))


def extract_external_urls(text: str, post_url: str | None) -> list[str]:
    urls = []
    for url in URL_RE.findall(text or ""):
        clean = canonical_url(url)
        if clean and not is_x_status_url(clean):
            urls.append(clean)
    if post_url:
        clean_post = canonical_url(post_url)
        if clean_post and not is_x_status_url(clean_post):
            urls.append(clean_post)
    return dedupe(urls)


def canonical_url(value: str) -> str | None:
    parsed = urlparse(value.strip().rstrip(".,;"))
    if not parsed.scheme or not parsed.netloc:
        return None
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    return urlunparse((parsed.scheme.lower(), netloc, path, "", "", ""))


def is_x_status_url(value: str) -> bool:
    parsed = urlparse(value)
    host = parsed.netloc.lower()
    return host in {"x.com", "twitter.com", "www.x.com", "www.twitter.com"} and "/status/" in parsed.path


def max_metric(group: list[dict[str, Any]], name: str) -> int:
    values = []
    for post in group:
        try:
            values.append(int(post.get(name) or 0))
        except (TypeError, ValueError):
            values.append(0)
    return max(values or [0])


def split_csv(value: str | None) -> list[str]:
    return [part for part in (value or "").split(",") if part]


def normalize_space(value: str) -> str:
    return " ".join(value.split())


def snippet(value: str, length: int) -> str:
    value = normalize_space(value)
    if len(value) <= length:
        return value
    return value[: max(0, length - 1)].rstrip() + "..."


def stable_id(group_key_value: str, post_ids: list[str]) -> str:
    payload = json.dumps([group_key_value, sorted(post_ids)], sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def parse_raw_json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def dedupe(values) -> list[Any]:
    seen = set()
    output = []
    for value in values:
        if value in (None, "") or value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output
