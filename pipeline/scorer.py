"""Scoring node: two-pass LLM scoring with keyword fallback."""

import asyncio
import hashlib
import json
import os
import re

from pipeline.cost_tracker import tracker as cost_tracker

from config import (
    DEAL_KEYWORDS,
    FMCG_KEYWORDS,
    MODEL,
    OPENROUTER_BASE_URL,
    OUTPUT_DIR,
    RELEVANCE_CUTOFF,
)

_CACHE_PATH = OUTPUT_DIR / "llm_cache.json"
_TRIAGE_CACHE_PATH = OUTPUT_DIR / "triage_cache.json"


def _load_cache() -> dict:
    """Load the LLM analysis cache from disk."""
    if _CACHE_PATH.exists():
        try:
            return json.loads(_CACHE_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_cache(cache: dict) -> None:
    """Persist the LLM analysis cache to disk."""
    _CACHE_PATH.parent.mkdir(exist_ok=True)
    _CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False))


def _load_triage_cache() -> dict:
    if _TRIAGE_CACHE_PATH.exists():
        try:
            return json.loads(_TRIAGE_CACHE_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_triage_cache(cache: dict) -> None:
    _TRIAGE_CACHE_PATH.parent.mkdir(exist_ok=True)
    _TRIAGE_CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False))


def _cache_key(article: dict) -> str:
    """Derive a stable cache key from an article's URL or title+source."""
    url = article.get("url", "")
    if url:
        return url
    raw = f"{article.get('title', '')}|{article.get('source', '')}"
    return hashlib.md5(raw.encode()).hexdigest()


def _keyword_score(article: dict) -> tuple[float, str]:
    """Score article relevance using keyword matching (no-API fallback)."""
    text = f"{article.get('title', '')} {article.get('content', '')}".lower()

    fmcg_hits = sum(1 for kw in FMCG_KEYWORDS if kw in text)
    fmcg_score = min(fmcg_hits / 3, 1.0)

    deal_hits = sum(1 for kw in DEAL_KEYWORDS if kw in text)
    deal_score = min(deal_hits / 2, 1.0)

    total = (fmcg_score * 0.5) + (deal_score * 0.5)

    reasoning_parts = []
    if fmcg_hits > 0:
        reasoning_parts.append(f"FMCG keywords: {fmcg_hits}")
    if deal_hits > 0:
        reasoning_parts.append(f"Deal keywords: {deal_hits}")
    reasoning = "; ".join(reasoning_parts) if reasoning_parts else "No keyword matches"

    return round(total, 3), reasoning


_STRUCTURED_FIELDS = [
    "deal_type", "acquirer", "target", "deal_value_structured",
    "deal_status", "sector", "key_insight", "why_it_matters", "story_angle",
    "headline_summary",
]


def _keyword_article_stub(article: dict) -> None:
    """Set all structured extraction fields to None on an article dict."""
    for field in _STRUCTURED_FIELDS:
        article[field] = None


# ---------------------------------------------------------------------------
# Pass 1: LLM triage — batch titles for cheap relevance check
# ---------------------------------------------------------------------------

_TRIAGE_BATCH_SIZE = 20  # titles per triage call
_TRIAGE_CONCURRENCY = 5


def _build_triage_prompt(batch: list[dict]) -> str:
    """Build a triage prompt for a batch of article titles."""
    items = []
    for i, article in enumerate(batch, 1):
        title = article.get("title", "Untitled")
        source = article.get("source", "Unknown")
        items.append(f"{i}. [{source}] {title}")

    article_list = "\n".join(items)

    return f"""You are an FMCG M&A deal screener. Your job is to quickly identify which articles are likely about real FMCG/consumer goods deals (acquisitions, mergers, investments, divestitures, JVs, IPOs, partnerships).

Here are {len(batch)} article titles with their sources:

{article_list}

For each article, decide: is this likely about a specific FMCG/consumer goods M&A deal or transaction?

Return ONLY a JSON array of objects, one per article, in order:
[{{"id": 1, "pass": true, "reason": "Henkel acquiring hair care brand"}}, {{"id": 2, "pass": false, "reason": "AI/tech article, not a deal"}}]

Rules:
- "pass": true if the title suggests a specific deal, transaction, acquisition, merger, investment, stake sale, or partnership involving FMCG/consumer goods/food/beverage/personal care companies
- "pass": false for general industry news, opinion pieces, tech/AI articles, hiring news, earnings reports, or non-FMCG sectors
- Be inclusive — if uncertain, pass it through (better to over-include than miss a deal)

Return ONLY the JSON array, no markdown fences."""


def _parse_triage_response(content: str, batch_size: int) -> list[bool]:
    """Parse triage response into a list of pass/fail booleans."""
    json_match = re.search(r'\[.*\]', content, re.DOTALL)
    if not json_match:
        # If parsing fails, pass everything through
        return [True] * batch_size

    try:
        results = json.loads(json_match.group())
        passes = [True] * batch_size
        for item in results:
            idx = item.get("id", 0) - 1
            if 0 <= idx < batch_size:
                passes[idx] = item.get("pass", True)
        return passes
    except (json.JSONDecodeError, KeyError):
        return [True] * batch_size


async def _triage_batch_async(
    batch: list[dict], llm, batch_idx: int, total_batches: int,
    semaphore: asyncio.Semaphore,
) -> list[bool]:
    """Run triage on a batch of articles."""
    async with semaphore:
        print(f"    [triage] Batch {batch_idx}/{total_batches} ({len(batch)} articles)")
        prompt = _build_triage_prompt(batch)
        try:
            response = await asyncio.wait_for(llm.ainvoke(prompt), timeout=30)
            cost_tracker.record(response)
            results = _parse_triage_response(response.content.strip(), len(batch))
            passed = sum(1 for r in results if r)
            print(f"    [triage] Batch {batch_idx}: {passed}/{len(batch)} passed")
            return results
        except Exception as e:
            print(f"    [triage] Batch {batch_idx} failed ({e}), passing all through")
            return [True] * len(batch)


def _run_triage(articles: list[dict], llm) -> list[dict]:
    """Pass 1: LLM triage to filter articles by relevance using batched title screening."""
    triage_cache = _load_triage_cache()

    # Split into cached and uncached
    cached_results = {}
    uncached_articles = []
    uncached_indices = []

    for i, article in enumerate(articles):
        key = _cache_key(article)
        if key in triage_cache:
            cached_results[i] = triage_cache[key]
        else:
            uncached_articles.append(article)
            uncached_indices.append(i)

    if cached_results:
        print(f"  [triage] {len(cached_results)} cached, {len(uncached_articles)} need triage")

    # Batch uncached articles for triage
    triage_results = {}
    if uncached_articles:
        batches = [
            uncached_articles[i:i + _TRIAGE_BATCH_SIZE]
            for i in range(0, len(uncached_articles), _TRIAGE_BATCH_SIZE)
        ]
        print(f"  [triage] Pass 1: Screening {len(uncached_articles)} articles "
              f"in {len(batches)} batches...")

        semaphore = asyncio.Semaphore(_TRIAGE_CONCURRENCY)
        tasks = [
            _triage_batch_async(batch, llm, i + 1, len(batches), semaphore)
            for i, batch in enumerate(batches)
        ]

        loop = asyncio.get_event_loop()
        batch_results = loop.run_until_complete(asyncio.gather(*tasks))

        # Map results back
        flat_idx = 0
        for batch_passes in batch_results:
            for passes in batch_passes:
                orig_idx = uncached_indices[flat_idx]
                triage_results[orig_idx] = passes
                triage_cache[_cache_key(articles[orig_idx])] = passes
                flat_idx += 1

        _save_triage_cache(triage_cache)

    # Merge cached + fresh results
    passed = []
    for i, article in enumerate(articles):
        if i in cached_results:
            passes = cached_results[i]
        elif i in triage_results:
            passes = triage_results[i]
        else:
            passes = True  # safety fallback

        article["triage_passed"] = passes
        if passes:
            passed.append(article)

    triaged_out = len(articles) - len(passed)
    print(f"  [triage] Pass 1 result: {len(passed)} passed, {triaged_out} filtered out")
    return passed


# ---------------------------------------------------------------------------
# Pass 2: Full LLM analysis (same as before)
# ---------------------------------------------------------------------------

_LLM_CONCURRENCY = 5
_LLM_TIMEOUT = 60


def _build_prompt(article: dict) -> str:
    """Build the LLM analysis prompt for a single article."""
    content = article.get("content", "") or ""
    truncated_content = content[:4000]

    return f"""You are an FMCG M&A analyst extracting structured deal intelligence.

Analyze this article and return structured data.

Title: {article.get('title', '')}
Source: {article.get('source', 'Unknown')}
Content: {truncated_content}

Scoring guide:
- 0.9-1.0: Core FMCG M&A deal (acquisition, merger, JV between major FMCG companies)
- 0.7-0.8: FMCG-adjacent deal (PE investment in FMCG, divestiture, retail/distribution deal involving FMCG)
- 0.4-0.6: Tangentially related (investment not clearly M&A, or FMCG company but not a deal)
- 0.0-0.3: Not FMCG related (tech, pharma, other sectors)

Extraction instructions:
- deal_type: one of acquisition|merger|jv|investment|divestiture|ipo|partnership|other
- acquirer: the active party (investor, buyer, acquirer) or null if unclear
- target: the target company or asset, or null if unclear
- deal_value_structured: normalized value string (e.g. "$2.1B", "€500M", "₹1,200 Cr") or "Undisclosed"
- deal_status: one of announced|completed|rumored|in-progress
- sector: FMCG sub-sector (e.g. "Dairy & Nutrition", "Personal Care", "Snacks & Confectionery")
- key_insight: one-line compelling summary for a newsletter
- why_it_matters: strategic rationale / what makes this notable
- story_angle: what makes this deal noteworthy — record size, unlikely buyer, market shift, regulatory angle, first in category, etc. If nothing stands out, say "Standard sector transaction."
- headline_summary: 3-4 sentence factual summary covering the key deal facts, parties involved, financial details, and context. This will be used directly in a newsletter — be specific and cite numbers/names from the article.

Return ONLY valid JSON, no markdown fences:
{{"relevance_score": 0.85, "relevance_reasoning": "brief reason", "deal_type": "acquisition", "acquirer": "Company A", "target": "Company B", "deal_value_structured": "$2.1B", "deal_status": "announced", "sector": "Dairy & Nutrition", "key_insight": "...", "why_it_matters": "...", "story_angle": "...", "headline_summary": "..."}}"""


def _parse_llm_response(content_text: str) -> dict:
    """Parse and validate the JSON response from the LLM."""
    json_match = re.search(r'\{.*\}', content_text, re.DOTALL)
    if not json_match:
        raise ValueError("No JSON object found in LLM response")

    result = json.loads(json_match.group())

    if "relevance_score" not in result:
        raise ValueError("Missing relevance_score in LLM response")

    return result


async def _llm_analyze_async(
    article: dict, llm, idx: int, total: int, semaphore: asyncio.Semaphore,
) -> dict:
    """Async LLM analysis for a single article, with concurrency + timeout."""
    title = article.get('title', '')[:60]

    async with semaphore:
        print(f"    [scorer] Analyzing article {idx}/{total}: {title}")
        prompt = _build_prompt(article)
        try:
            response = await asyncio.wait_for(
                llm.ainvoke(prompt), timeout=_LLM_TIMEOUT,
            )
            cost_tracker.record(response)
            result = _parse_llm_response(response.content.strip())
            print(f"    [scorer] Done {idx}/{total}: {title}")
            return result
        except asyncio.TimeoutError:
            print(f"    [scorer] Timeout after {_LLM_TIMEOUT}s for '{title}'")
        except Exception as e:
            print(f"    [scorer] Failed for '{title}': {e}")

        score, reasoning = _keyword_score(article)
        fallback = {"relevance_score": score, "relevance_reasoning": reasoning}
        for field in _STRUCTURED_FIELDS:
            fallback[field] = None
        return fallback


# ---------------------------------------------------------------------------
# Main scoring node
# ---------------------------------------------------------------------------

def score_node(state: dict) -> dict:
    """LangGraph node: two-pass LLM scoring.

    Pass 1 (triage): Batch article titles → LLM screens for FMCG deal relevance.
    Pass 2 (analysis): Full content analysis on articles that passed triage.
    """
    import pandas as pd

    articles = state.get("deduplicated_articles", [])
    no_api = state.get("metadata", {}).get("no_api", False)
    use_llm = not no_api and os.getenv("OPENROUTER_API_KEY")

    all_articles = [dict(a) for a in articles]

    if use_llm:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=MODEL,
            temperature=0,
            openai_api_key=os.getenv("OPENROUTER_API_KEY"),
            openai_api_base=OPENROUTER_BASE_URL,
        )

        # Pass 1: LLM triage
        triaged = _run_triage(all_articles, llm)

        # Pass 2: Full LLM analysis on triaged articles
        cache = _load_cache()

        cached_articles = []
        uncached_articles = []
        for article in triaged:
            key = _cache_key(article)
            if key in cache:
                cached_articles.append((article, cache[key]))
            else:
                uncached_articles.append(article)

        if cached_articles:
            print(f"  [scorer] {len(cached_articles)} cached, "
                  f"{len(uncached_articles)} need full analysis")

        if uncached_articles:
            print(f"  [scorer] Pass 2: Analyzing {len(uncached_articles)} articles "
                  f"(max {_LLM_CONCURRENCY} concurrent, {_LLM_TIMEOUT}s timeout)...")
            semaphore = asyncio.Semaphore(_LLM_CONCURRENCY)
            tasks = [
                _llm_analyze_async(a, llm, i + 1, len(uncached_articles), semaphore)
                for i, a in enumerate(uncached_articles)
            ]
            results = asyncio.get_event_loop().run_until_complete(asyncio.gather(*tasks))

            for article, result in zip(uncached_articles, results):
                cache[_cache_key(article)] = result

            _save_cache(cache)

        # Apply results
        scored = []
        for article in triaged:
            result = cache[_cache_key(article)]
            article["relevance_score"] = result["relevance_score"]
            article["relevance_reasoning"] = result.get("relevance_reasoning", "")
            for field in _STRUCTURED_FIELDS:
                article[field] = result.get(field)
            scored.append(article)
    else:
        # Keyword-only mode
        print("  [scorer] Using keyword-based scoring (no-API mode)")
        scored = []
        for article in all_articles:
            score, reasoning = _keyword_score(article)
            article["relevance_score"] = score
            article["relevance_reasoning"] = reasoning
            _keyword_article_stub(article)
            scored.append(article)

    # Filter by relevance cutoff
    relevant = [a for a in scored if a["relevance_score"] >= RELEVANCE_CUTOFF]
    filtered_out = len(scored) - len(relevant)

    # Sort by relevance score descending
    relevant.sort(key=lambda x: x["relevance_score"], reverse=True)

    # Save scored data
    OUTPUT_DIR.mkdir(exist_ok=True)
    pd.DataFrame(scored).to_csv(OUTPUT_DIR / "scored_deals.csv", index=False)

    print(f"  [scorer] Scored {len(scored)} articles, {len(relevant)} above cutoff "
          f"({filtered_out} filtered out)")

    metadata = {**state.get("metadata", {})}
    metadata["scored_count"] = len(relevant)
    metadata["filtered_out"] = filtered_out
    metadata["scoring_method"] = "llm-two-pass" if use_llm else "keyword"

    return {
        "scored_articles": relevant,
        "output_paths": {
            **state.get("output_paths", {}),
            "scored_csv": str(OUTPUT_DIR / "scored_deals.csv"),
        },
        "metadata": metadata,
    }
