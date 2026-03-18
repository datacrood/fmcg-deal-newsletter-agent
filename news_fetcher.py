"""News fetching: NewsAPI + Google News RSS + fallback JSON."""
from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

import feedparser
import requests
import trafilatura
from googlenewsdecoder import new_decoderv1

FALLBACK_PATH = Path(__file__).parent / "output" / "raw_deals.json"
MAX_CONTENT_LEN = 15_000  # skip articles exceeding this limit
NEWSAPI_PAGE_SIZE = int(os.getenv("NEWSAPI_PAGE_SIZE", "10"))
RSS_MAX_PER_FEED = int(os.getenv("RSS_MAX_PER_FEED", "10"))
DAYS_BACK = int(os.getenv("DAYS_BACK", "14"))


def _strip_html(text: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    clean = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", clean).strip()


def _resolve_google_news_url(google_url: str) -> str:
    """Decode Google News URL to get the actual article URL."""
    try:
        result = new_decoderv1(google_url)
        if result.get("status") and result.get("decoded_url"):
            return result["decoded_url"]
    except Exception as e:
        print(f"    [rss] Failed to decode Google News URL: {e}")
    return google_url


def _extract_full_text(url: str) -> str | None:
    """Extract article text using trafilatura."""
    print(f"    [trafilatura] Extracting text from {url[:80]} ...")
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded, include_comments=False)
            if text:
                if len(text) > MAX_CONTENT_LEN:
                    print(f"    [trafilatura] Skipped — {len(text)} chars exceeds {MAX_CONTENT_LEN} limit")
                    return None
                print(f"    [trafilatura] OK — {len(text)} chars extracted")
            else:
                print(f"    [trafilatura] No text could be extracted")
            return text
    except Exception as e:
        print(f"    [trafilatura] FAILED for {url[:80]}: {e}")
    return None


def fetch_from_newsapi(
    query: str = "(FMCG OR \"consumer goods\" OR CPG) AND (acquisition OR merger OR takeover OR \"stake sale\" OR buyout)",
    days_back: int | None = None,
    page_size: int | None = None,
) -> list[dict]:
    """Fetch articles from NewsAPI.org."""
    api_key = os.getenv("NEWSAPI_KEY")
    if not api_key:
        print("  [newsapi] NEWSAPI_KEY not set, skipping")
        return []

    limit = min(max(page_size or NEWSAPI_PAGE_SIZE, 1), 100)
    days_back = days_back or DAYS_BACK
    from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    params = {
        "q": query,
        "from": from_date,
        "sortBy": "relevancy",
        "language": "en",
        "pageSize": limit,
        "apiKey": api_key,
    }

    print(f"  [newsapi] Fetching articles (query={query!r}, from={from_date}) ...")
    try:
        resp = requests.get("https://newsapi.org/v2/everything", params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        print(f"  [newsapi] API responded with {data.get('totalResults', '?')} total results")
        raw_articles = data.get("articles", [])
        print(f"  [newsapi] Extracting full text for {len(raw_articles)} articles ({_RSS_WORKERS} threads)...")

        def _process_newsapi_article(i_art):
            i, art = i_art
            source_name = art.get("source", {}).get("name", "Unknown")
            source_url = art.get("url", "")
            domain = urlparse(source_url).netloc.replace("www.", "") if source_url else ""
            title = art.get("title", "")

            content = _strip_html(art.get("content") or art.get("description") or "")
            full_text = _extract_full_text(source_url)
            if full_text:
                content = full_text

            if len(content) > MAX_CONTENT_LEN:
                return None

            return {
                "id": f"newsapi_{i:03d}",
                "title": title,
                "source": source_name,
                "source_domain": domain,
                "published_date": (art.get("publishedAt") or "")[:10],
                "url": source_url,
                "content": content,
                "fetch_method": "newsapi",
            }

        articles = []
        with ThreadPoolExecutor(max_workers=_RSS_WORKERS) as pool:
            for result in pool.map(_process_newsapi_article, enumerate(raw_articles)):
                if result:
                    articles.append(result)
                    print(f"  [newsapi] [{len(articles)}] {result['title'][:80]}")

        print(f"  [newsapi] Done — {len(articles)} articles fetched")
        return articles
    except Exception as e:
        print(f"  [newsapi] FAILED: {e}")
        return []


_RSS_WORKERS = 6  # parallel threads for URL resolution + text extraction


def _process_rss_entry(entry: dict, cutoff: datetime) -> dict | None:
    """Process a single RSS entry: resolve URL, extract full text. Returns article dict or None."""
    pub = entry.get("published", "")
    if pub:
        try:
            pub_dt = parsedate_to_datetime(pub)
            if pub_dt.replace(tzinfo=None) < cutoff:
                return None
        except Exception:
            pass

    raw_url = entry.get("link", "")
    title = _strip_html(entry.get("title", ""))

    actual_url = _resolve_google_news_url(raw_url) if raw_url else ""

    source = entry.get("source", {}).get("title", "Google News")
    domain = urlparse(actual_url).netloc.replace("www.", "") if actual_url else ""
    content = _strip_html(entry.get("summary", ""))

    full_text = _extract_full_text(actual_url) if actual_url else None
    if full_text:
        content = full_text

    if len(content) > MAX_CONTENT_LEN:
        return None

    return {
        "title": title,
        "source": source,
        "source_domain": domain,
        "published_date": pub[:10] if pub else "",
        "url": actual_url,
        "content": content,
        "fetch_method": "rss",
    }


def fetch_from_rss(max_per_feed: int | None = None, days_back: int | None = None) -> list[dict]:
    """Fetch from Google News RSS feeds for FMCG deals."""
    limit = max_per_feed or RSS_MAX_PER_FEED
    days_back = days_back or DAYS_BACK
    cutoff = datetime.now() - timedelta(days=days_back)
    feeds = [
        "https://news.google.com/rss/search?q=FMCG+acquisition+merger&hl=en-IN&gl=IN&ceid=IN:en",
        "https://news.google.com/rss/search?q=consumer+goods+acquisition+deal&hl=en&gl=US&ceid=US:en",
    ]

    # Collect entries from all feeds (fast, just XML parsing)
    all_entries = []
    for feed_idx, feed_url in enumerate(feeds, 1):
        print(f"  [rss] Fetching feed {feed_idx}/{len(feeds)}: {feed_url[:80]} ...")
        try:
            feed = feedparser.parse(feed_url)
            entries = feed.entries[:limit]
            print(f"  [rss] Feed {feed_idx} returned {len(feed.entries)} entries (taking {len(entries)})")
            all_entries.extend(entries)
        except Exception as e:
            print(f"  [rss] FAILED for feed {feed_idx}: {e}")

    # Process entries in parallel (URL resolution + full text extraction)
    articles = []
    print(f"  [rss] Processing {len(all_entries)} entries ({_RSS_WORKERS} threads)...")
    with ThreadPoolExecutor(max_workers=_RSS_WORKERS) as pool:
        futures = {pool.submit(_process_rss_entry, e, cutoff): e for e in all_entries}
        for future in as_completed(futures):
            try:
                result = future.result()
                if result:
                    result["id"] = f"rss_{len(articles):03d}"
                    articles.append(result)
                    print(f"  [rss] [{len(articles)}] {result['title'][:60]} -> {result['source_domain']}")
            except Exception as e:
                print(f"  [rss] Entry processing failed: {e}")

    print(f"  [rss] Done — {len(articles)} articles from {len(feeds)} feeds")
    return articles


def fetch_fallback() -> list[dict]:
    """Load curated fallback dataset."""
    print(f"  [fallback] Loading from {FALLBACK_PATH} ...")
    with open(FALLBACK_PATH) as f:
        articles = json.load(f)
    for art in articles:
        art["fetch_method"] = "fallback"
    print(f"  [fallback] Loaded {len(articles)} articles")
    return articles
