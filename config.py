"""Central configuration — all constants live here."""

# Deduplication
SIMILARITY_THRESHOLD_TFIDF = 0.30  # Cosine similarity threshold for TF-IDF dedup

# Source credibility tiers (lower = better) — not used in dedup currently
SOURCE_TIERS = {
    "tier_1": [
        "Reuters", "Bloomberg", "Financial Times", "WSJ",
        "Economic Times", "CNBC", "Wall Street Journal",
    ],
    "tier_2": [
        "Moneycontrol", "Business Standard", "LiveMint", "Food Navigator",
        "Just Food", "Mint", "The Hindu BusinessLine", "Forbes",
        "Food Dive", "Dairy Reporter", "BeverageDaily",
    ],
    # Everything else defaults to tier_3
}
