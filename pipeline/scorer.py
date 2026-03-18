"""Scoring node: LLM-based or keyword-based relevance scoring."""

import hashlib
import json
import os
import re

from config import (
    CREDIBILITY_CUTOFF,
    DEAL_KEYWORDS,
    FMCG_KEYWORDS,
    MODEL,
    OPENROUTER_BASE_URL,
    OUTPUT_DIR,
    RELEVANCE_CUTOFF,
    SOURCE_TIERS,
)

_CACHE_PATH = OUTPUT_DIR / "llm_cache.json"


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


def _cache_key(article: dict) -> str:
    """Derive a stable cache key from an article's URL or title+source."""
    url = article.get("url", "")
    if url:
        return url
    # Fallback: hash title+source for articles without URLs
    raw = f"{article.get('title', '')}|{article.get('source', '')}"
    return hashlib.md5(raw.encode()).hexdigest()

def _credibility_check(article: dict) -> tuple[float, bool]:
    """Check if article is credible enough for LLM scoring.

    Returns (credibility_score, passes_filter).
    Auto-passes corroborated articles (corroboration_count >= 2).
    """
    corroboration_count = article.get("corroboration_count", 1)
    if corroboration_count >= 2:
        # Corroborated by multiple sources — auto-pass
        # Base 0.8 for 2 sources, +0.05 per additional source, capped at 1.0
        score = min(0.8 + (corroboration_count - 2) * 0.05, 1.0)
        return score, True

    domain = article.get("source_domain", "")
    # Strip leading "m." so mobile subdomains match (e.g. m.economictimes.com)
    if domain.startswith("m."):
        domain = domain[2:]
    score = SOURCE_TIERS.get(domain, SOURCE_TIERS["default"])
    return score, score >= CREDIBILITY_CUTOFF


def _keyword_score(article: dict) -> tuple[float, str]:
    """Score article relevance using keyword matching (no-API fallback)."""
    text = f"{article.get('title', '')} {article.get('content', '')}".lower()

    # FMCG relevance (0.5 weight)
    fmcg_hits = sum(1 for kw in FMCG_KEYWORDS if kw in text)
    fmcg_score = min(fmcg_hits / 3, 1.0)

    # Deal relevance (0.5 weight)
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


def _llm_analyze(article: dict) -> dict:
    """Score and extract structured deal data from a single article via LLM.

    Returns dict with relevance_score, relevance_reasoning, and structured fields.
    On failure, falls back to keyword scoring + null structured fields.
    """
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        model=MODEL,
        temperature=0,
        openai_api_key=os.getenv("OPENROUTER_API_KEY"),
        openai_api_base=OPENROUTER_BASE_URL,
    )

    content = article.get("content", "") or ""
    truncated_content = content[:4000]

    prompt = f"""You are an FMCG M&A analyst extracting structured deal intelligence.

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

    try:
        response = llm.invoke(prompt)
        content_text = response.content.strip()

        json_match = re.search(r'\{.*\}', content_text, re.DOTALL)
        if not json_match:
            raise ValueError("No JSON object found in LLM response")

        result = json.loads(json_match.group())

        # Validate required fields
        if "relevance_score" not in result:
            raise ValueError("Missing relevance_score in LLM response")

        return result
    except Exception as e:
        print(f"    [scorer] LLM analysis failed for '{article.get('title', '')[:60]}': {e}")
        # Fall back to keyword scoring + null structured fields
        score, reasoning = _keyword_score(article)
        fallback = {"relevance_score": score, "relevance_reasoning": reasoning}
        for field in _STRUCTURED_FIELDS:
            fallback[field] = None
        return fallback


def score_node(state: dict) -> dict:
    """LangGraph node: score and filter articles by relevance."""
    import pandas as pd  # lazy: only needed when this node runs

    articles = state.get("deduplicated_articles", [])
    no_api = state.get("metadata", {}).get("no_api", False)
    use_llm = not no_api and os.getenv("OPENROUTER_API_KEY")

    # Split articles by credibility
    credible = []
    non_credible = []
    for article in articles:
        a = dict(article)
        cred_score, passes = _credibility_check(a)
        a["credibility_score"] = round(cred_score, 3)
        a["credibility_passed"] = passes
        if passes:
            credible.append(a)
        else:
            non_credible.append(a)

    print(f"  [scorer] Credibility filter: {len(credible)} passed, "
          f"{len(non_credible)} discarded")

    # Score credible articles with LLM or keywords
    scored = []
    if use_llm and credible:
        cache = _load_cache()
        cache_hits = 0
        print(f"  [scorer] Using LLM-based analysis for {len(credible)} credible articles")
        for i, article in enumerate(credible):
            key = _cache_key(article)
            if key in cache:
                result = cache[key]
                cache_hits += 1
                print(f"    [scorer] Cache hit {i+1}/{len(credible)}: "
                      f"{article.get('title', '')[:60]}")
            else:
                print(f"    [scorer] Analyzing article {i+1}/{len(credible)}: "
                      f"{article.get('title', '')[:60]}")
                result = _llm_analyze(article)
                cache[key] = result
            article["relevance_score"] = result["relevance_score"]
            article["relevance_reasoning"] = result.get("relevance_reasoning", "")
            for field in _STRUCTURED_FIELDS:
                article[field] = result.get(field)
            scored.append(article)
        _save_cache(cache)
        if cache_hits:
            print(f"  [scorer] {cache_hits} cached, {len(credible) - cache_hits} new LLM calls")
    else:
        if credible:
            print("  [scorer] Using keyword-based scoring (no-API mode)")
        for article in credible:
            score, reasoning = _keyword_score(article)
            article["relevance_score"] = score
            article["relevance_reasoning"] = reasoning
            _keyword_article_stub(article)
            scored.append(article)

    print(f"  [scorer] Discarded {len(non_credible)} non-credible articles")

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
    metadata["scoring_method"] = "llm" if use_llm else "keyword"

    return {
        "scored_articles": relevant,
        "output_paths": {
            **state.get("output_paths", {}),
            "scored_csv": str(OUTPUT_DIR / "scored_deals.csv"),
        },
        "metadata": metadata,
    }
