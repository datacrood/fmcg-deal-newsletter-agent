# FMCG Deal Pulse

Automated newsletter pipeline that discovers, scores, and summarizes FMCG M&A deals.

## Overview

The pipeline ingests articles from NewsAPI and Google News RSS, deduplicates them using TF-IDF cosine similarity, scores relevance via LLM (with keyword fallback), and generates a Substack-style Markdown newsletter.

## Pipeline Architecture

```
ingest → dedup → score → newsletter
```

1. **Ingest** — Fetches articles from NewsAPI, Google News RSS feeds, or a fallback JSON dataset. Performs URL-level deduplication across sources.
2. **Dedup** — TF-IDF vectorization + cosine similarity to cluster near-duplicate articles. Keeps the best source per cluster and tracks corroboration counts.
3. **Score** — LLM-based structured extraction (deal type, acquirer, target, value, sector) with keyword-only fallback. Filters by source credibility and relevance cutoff.
4. **Newsletter** — Assembles a Markdown newsletter with headline deal, briefs, sector pulse, watchlist, and executive summary. LLM-generated narrative sections with template fallbacks.

Built on [LangGraph](https://github.com/langchain-ai/langgraph) for orchestration.

## Setup

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

Copy `.env.example` to `.env` and fill in the API keys:

```bash
cp .env.example .env
```

## Usage

```bash
# Live mode — fetches from NewsAPI + RSS (requires API keys)
python main.py

# Demo mode — uses fallback dataset, no API keys needed
python main.py --demo
```

## Output

All generated files go to `output/`:

| File | Description |
|---|---|
| `raw_deals.json` | Raw ingested articles |
| `deduped_deals.json` | After TF-IDF deduplication |
| `scored_deals.csv` | All articles with scores and structured fields |
| `newsletter.md` | Final newsletter in Markdown |
| `llm_cache.json` | Cached LLM responses (avoids re-scoring) |

## Configuration

All tunable parameters live in `config.py`:

- `SIMILARITY_THRESHOLD_TFIDF` — Cosine similarity threshold for dedup (default: 0.30)
- `RELEVANCE_CUTOFF` — Minimum score to include in newsletter (default: 0.65)
- `CREDIBILITY_CUTOFF` — Minimum source credibility for LLM scoring (default: 0.50)
- `MODEL` — LLM model for scoring and newsletter generation
- `FMCG_KEYWORDS` / `DEAL_KEYWORDS` — Keyword lists for fallback scoring
- `SOURCE_TIERS` — Domain credibility scores

## Testing

```bash
pytest test/
```
