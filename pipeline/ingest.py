"""Ingest node: fetch articles from NewsAPI, RSS, and fallback."""

from __future__ import annotations

import json
from datetime import datetime

from config import OUTPUT_DIR
from news_fetcher import fetch_from_newsapi, fetch_from_rss, fetch_fallback


def _url_dedup(articles: list[dict]) -> list[dict]:
    """Deduplicate by URL, keeping the version with the longest content."""
    best: dict[str, dict] = {}
    no_url = []
    for art in articles:
        url = art.get("url", "")
        if not url:
            no_url.append(art)
            continue
        existing = best.get(url)
        if not existing or len(art.get("content", "")) > len(existing.get("content", "")):
            best[url] = art
    return list(best.values()) + no_url


def _save_raw(articles: list[dict]) -> Path:
    """Save raw articles to JSON and return the path."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    json_path = OUTPUT_DIR / "raw_deals.json"
    with open(json_path, "w") as f:
        json.dump(articles, f, indent=2)
    return json_path


def ingest_node(state: dict) -> dict:
    """LangGraph node: ingest articles from all available sources."""
    demo = state.get("metadata", {}).get("demo", False)
    all_articles: list[dict] = []
    sources_used: list[str] = []

    if demo:
        all_articles = fetch_fallback()
        sources_used.append("fallback")
    else:
        newsapi_articles = fetch_from_newsapi()
        if newsapi_articles:
            all_articles.extend(newsapi_articles)
            sources_used.append("newsapi")

        rss_articles = fetch_from_rss()
        if rss_articles:
            all_articles.extend(rss_articles)
            sources_used.append("rss")

        if not all_articles:
            all_articles = fetch_fallback()
            sources_used.append("fallback")

    # URL-level dedup across sources
    before_dedup = len(all_articles)
    all_articles = _url_dedup(all_articles)
    dedup_removed = before_dedup - len(all_articles)

    json_path = _save_raw(all_articles)

    metadata = {**state.get("metadata", {})}
    metadata["ingested_count"] = len(all_articles)
    metadata["sources_used"] = sources_used
    metadata["url_dedup_removed"] = dedup_removed
    metadata["ingested_at"] = datetime.now().isoformat()

    print(f"  [ingest] {len(all_articles)} articles from {', '.join(sources_used)} -> {json_path}")

    return {
        "raw_articles": all_articles,
        "output_paths": {**state.get("output_paths", {}), "raw_json": str(json_path)},
        "metadata": metadata,
    }
