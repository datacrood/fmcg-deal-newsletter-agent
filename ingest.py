"""Ingestion node: combine articles from NewsAPI, RSS, and demo dataset."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from news_fetcher import fetch_from_newsapi, fetch_from_rss, fetch_fallback

OUTPUT_DIR = Path(__file__).parent / "output"

FMCG_KEYWORDS = [
    "fmcg", "consumer good", "consumer product", "packaged good", "cpg",
    "food & beverage", "food and beverage", "personal care", "home care",
    "hul", "hindustan unilever", "nestle", "p&g", "procter & gamble",
    "itc", "dabur", "godrej", "marico", "britannia", "colgate",
    "pepsico", "coca-cola", "mondelez", "unilever", "reckitt",
    "d2c", "direct to consumer", "direct-to-consumer",
]
DEAL_KEYWORDS = [
    "acquisition", "acquire", "acquired", "acquires",
    "merger", "merge", "merged", "merges",
    "takeover", "buyout", "stake sale", "stake buy",
    "investment", "invests", "invested",
    "joint venture", "partnership", "deal",
    "divestiture", "divest", "divests",
    "m&a", "buyback",
]


def _is_relevant(article: dict) -> bool:
    """Check if article is related to FMCG deals."""
    text = (article.get("title", "") + " " + article.get("content", "")[:1500]).lower()
    has_fmcg = any(k in text for k in FMCG_KEYWORDS)
    has_deal = any(k in text for k in DEAL_KEYWORDS)
    return has_fmcg and has_deal


def _dedup(articles: list[dict]) -> list[dict]:
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

    # Dedup across sources — keeps version with longest content
    before_dedup = len(all_articles)
    all_articles = _dedup(all_articles)
    dedup_removed = before_dedup - len(all_articles)

    # Relevance filter
    # before_filter = len(all_articles)
    # all_articles = [a for a in all_articles if _is_relevant(a)]
    # filtered_out = before_filter - len(all_articles)

    # print(f"  [ingest] Dedup removed {dedup_removed}, relevance filter removed {filtered_out}")

    json_path = _save_raw(all_articles)

    metadata = {**state.get("metadata", {})}
    metadata["ingested_count"] = len(all_articles)
    metadata["sources_used"] = sources_used
    metadata["dedup_removed"] = dedup_removed
    # metadata["filtered_out"] = filtered_out
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
    print(f"Dedup removed: {result['metadata']['dedup_removed']}")
    # print(f"Filtered out (irrelevant): {result['metadata']['filtered_out']}")
    print(f"Output:  {result['output_paths']['raw_json']}")


if __name__ == "__main__":
    main()
