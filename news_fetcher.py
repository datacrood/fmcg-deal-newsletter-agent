"""
News fetching tool: NewsAPI + Google News RSS + fallback JSON.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

import feedparser
import requests
import trafilatura

# print = logging.getprint(__name__)

FALLBACK_PATH = Path(__file__).parent.parent.parent / "data" / "fallback_deals.json"


def _content_hash(text: str) -> str:
    return hashlib.sha256(text[:1000].encode()).hexdigest()


def _extract_full_text(url: str) -> str | None:
    """Extract article text using trafilatura (F1: 0.958)."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            return trafilatura.extract(downloaded, include_comments=False)
    except Exception as e:
        print(f"trafilatura failed for {url}: {e}")
    return None


def fetch_from_newsapi(query: str = "FMCG AND (acquisition OR merger OR investment)", days_back: int = 14) -> list[dict]:
    """Fetch articles from NewsAPI.org."""
    api_key = os.getenv("NEWSAPI_KEY")
    if not api_key:
        print("NEWSAPI_KEY not set, skipping NewsAPI")
        return []

    from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "from": from_date,
        "sortBy": "relevancy",
        "language": "en",
        "pageSize": 50,
        "apiKey": api_key,
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        articles = []
        for i, art in enumerate(data.get("articles", [])):
            source_name = art.get("source", {}).get("name", "Unknown")
            source_url = art.get("url", "")
            domain = ""
            if source_url:
                from urllib.parse import urlparse
                domain = urlparse(source_url).netloc.replace("www.", "")

            # Try to extract full text
            content = art.get("content") or art.get("description") or ""
            full_text = _extract_full_text(source_url)
            if full_text:
                content = full_text

            articles.append({
                "id": f"newsapi_{i:03d}",
                "title": art.get("title", ""),
                "source": source_name,
                "source_domain": domain,
                "published_date": (art.get("publishedAt") or "")[:10],
                "url": source_url,
                "content": content,
                "content_hash": _content_hash(content) if content else "",
                "fetch_method": "newsapi",
            })
        print(f"NewsAPI returned {len(articles)} articles")
        return articles
    except Exception as e:
        print(f"NewsAPI fetch failed: {e}")
        return []


def fetch_from_rss() -> list[dict]:
    """Fetch from Google News RSS feed for FMCG deals."""
    feeds = [
        "https://news.google.com/rss/search?q=FMCG+acquisition+merger&hl=en-IN&gl=IN&ceid=IN:en",
        "https://news.google.com/rss/search?q=consumer+goods+acquisition+deal&hl=en&gl=US&ceid=US:en",
    ]
    articles = []
    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            for i, entry in enumerate(feed.entries[:25]):
                source = entry.get("source", {}).get("title", "Google News")
                url = entry.get("link", "")
                domain = ""
                if url:
                    from urllib.parse import urlparse
                    domain = urlparse(url).netloc.replace("www.", "")

                content = entry.get("summary", "")
                full_text = _extract_full_text(url)
                if full_text:
                    content = full_text

                articles.append({
                    "id": f"rss_{len(articles):03d}",
                    "title": entry.get("title", ""),
                    "source": source,
                    "source_domain": domain,
                    "published_date": entry.get("published", "")[:10] if entry.get("published") else "",
                    "url": url,
                    "content": content,
                    "content_hash": _content_hash(content) if content else "",
                    "fetch_method": "rss",
                })
            print(f"RSS feed returned {len(feed.entries)} entries")
        except Exception as e:
            print(f"RSS fetch failed for {feed_url}: {e}")
    return articles


def fetch_fallback() -> list[dict]:
    """Load curated fallback dataset."""
    with open(FALLBACK_PATH) as f:
        articles = json.load(f)
    for art in articles:
        art["content_hash"] = _content_hash(art.get("content", ""))
        art["fetch_method"] = "fallback"
    print(f"Loaded {len(articles)} fallback articles")
    return articles

if __name__=="__main__":
    # logging.basicConfig(level=logging.INFO)
    res = fetch_from_rss()
    print(f"Fetched {len(res)} articles")