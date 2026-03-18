"""Central configuration — all constants live here."""

from pathlib import Path

# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
OUTPUT_DIR = Path(__file__).parent / "output"
MODEL = "openai/gpt-4o-mini"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------
SIMILARITY_THRESHOLD_TFIDF = 0.30  # Cosine similarity threshold for TF-IDF dedup

# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
RELEVANCE_CUTOFF = 0.65  # Minimum score to include in newsletter

FMCG_KEYWORDS = [
    "fmcg", "consumer goods", "food", "beverage", "personal care",
    "household", "cpg", "packaged goods", "dairy", "snacks",
    "confectionery", "frozen food", "nutrition", "baby food",
    "skincare", "cosmetics", "detergent", "cleaning",
    "unilever", "nestlé", "nestle", "procter", "p&g", "danone",
    "mondelez", "pepsico", "coca-cola", "colgate", "reckitt",
    "kraft heinz", "general mills", "kellogg", "mars", "ferrero",
    "itc", "hindustan unilever", "dabur", "godrej", "britannia",
    "marico", "emami", "parle", "amul", "haldiram",
    "everest", "spice", "condiment", "sauce", "oil",
]

DEAL_KEYWORDS = [
    "acquisition", "acquire", "acquires", "acquired",
    "merger", "merge", "merged",
    "investment", "invests", "invested",
    "stake", "buyout", "buy out",
    "joint venture", "jv", "partnership",
    "deal", "transaction", "takeover",
    "divest", "divestiture", "sells",
    "ipo", "listing", "fundraise", "funding",
    "private equity", "pe fund", "venture capital",
    "billion", "million", "crore",
]

# Source credibility scores (domain-keyed, 0.0–1.0)
SOURCE_TIERS = {
    # Tier 1 — wire services / financial press
    "reuters.com": 0.95,
    "bloomberg.com": 0.95,
    "ft.com": 0.90,
    "wsj.com": 0.90,
    # Tier 2 — major business media
    "economictimes.com": 0.80,
    "livemint.com": 0.80,
    "cnbc.com": 0.80,
    "bbc.com": 0.80,
    # Tier 3 — business / industry press
    "moneycontrol.com": 0.75,
    "business-standard.com": 0.75,
    "thehindubusinessline.com": 0.75,
    "foodnavigator.com": 0.75,
    "fooddive.com": 0.75,
    "consumergoods.com": 0.75,
    "insidefmcg.com.au": 0.75,
    "cosmeticsbusiness.com": 0.70,
    # Tier 4 — general news / regional
    "ndtv.com": 0.70,
    "thehindu.com": 0.70,
    "financialexpress.com": 0.70,
    "forbes.com": 0.70,
    "theweek.in": 0.65,
    "goodreturns.in": 0.60,
    "entrepreneurindia.com": 0.60,
    "businessday.co.za": 0.65,
    "bizjournals.com": 0.65,
    "njbiz.com": 0.60,
    "ad-hoc-news.de": 0.55,
    # Tier 5 — consulting / research (good content but not news-first)
    "bain.com": 0.70,
    "bcg.com": 0.70,
    "pwc.com": 0.70,
    "mckinsey.com": 0.70,
    "default": 0.40,
}
CREDIBILITY_CUTOFF = 0.50  # Articles below this skip LLM scoring
