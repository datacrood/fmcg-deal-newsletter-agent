"""Ingestion node: combine articles from NewsAPI, RSS, and demo dataset."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from news_fetcher import fetch_from_newsapi, fetch_from_rss, fetch_fallback

OUTPUT_DIR = Path(__file__).parent / "output"


def _dedup(articles: list[dict]) -> list[dict]:
    """Remove duplicates by content_hash, keeping first occurrence."""
    seen: set[str] = set()
    unique = []
    for art in articles:
        h = art.get("content_hash", "")
        if not h or h not in seen:
            if h:
                seen.add(h)
            unique.append(art)
    return unique


def _save_raw(articles: list[dict]) -> Path:
    """Save raw articles to JSON and return the path."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    json_path = OUTPUT_DIR / "raw_deals.json"
    with open(json_path, "w") as f:
        json.dump(articles, f, indent=2)
    return json_path


def ingest_node(state: dict) -> dict:
    """LangGraph node: ingest articles from all available sources.

    When state["metadata"]["demo"] is True, skip live APIs and use the
    curated fallback dataset instead.
    """
    demo = state.get("metadata", {}).get("demo", False)
    all_articles: list[dict] = []
    sources_used: list[str] = []

    if demo:
        all_articles = fetch_fallback()
        sources_used.append("fallback")
    else:
        # Try both live sources and merge results
        newsapi_articles = fetch_from_newsapi()
        if newsapi_articles:
            all_articles.extend(newsapi_articles)
            sources_used.append("newsapi")

        rss_articles = fetch_from_rss()
        if rss_articles:
            all_articles.extend(rss_articles)
            sources_used.append("rss")

        # Fall back to curated dataset if nothing came back
        if not all_articles:
            all_articles = fetch_fallback()
            sources_used.append("fallback")

    # Deduplicate across sources
    all_articles = _dedup(all_articles)

    json_path = _save_raw(all_articles)

    metadata = {**state.get("metadata", {})}
    metadata["ingested_count"] = len(all_articles)
    metadata["sources_used"] = sources_used
    metadata["ingested_at"] = datetime.now().isoformat()

    print(f"  [ingest] {len(all_articles)} articles from {', '.join(sources_used)} -> {json_path}")

    return {
        "raw_articles": all_articles,
        "output_paths": {**state.get("output_paths", {}), "raw_json": str(json_path)},
        "metadata": metadata,
    }


def main():
    parser = argparse.ArgumentParser(description="Ingest FMCG deal articles")
    parser.add_argument("--demo", action="store_true", help="Use fallback dataset instead of live APIs")
    args = parser.parse_args()

    state: dict = {"metadata": {"demo": args.demo}, "output_paths": {}}
    result = ingest_node(state)

    print(f"\nIngested {result['metadata']['ingested_count']} articles")
    print(f"Sources: {', '.join(result['metadata']['sources_used'])}")
    print(f"Output:  {result['output_paths']['raw_json']}")


if __name__ == "__main__":
    main()
