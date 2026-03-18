"""Dedup node: TF-IDF based semantic near-duplicate detection.

Uses TF-IDF vectorization + cosine similarity to find clusters of
near-duplicate articles, then keeps the best source per cluster.
"""

from __future__ import annotations

import json

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from config import OUTPUT_DIR, SIMILARITY_THRESHOLD_TFIDF


def _make_text(article: dict) -> str:
    """Combine title + content for similarity computation."""
    title = article.get("title", "")
    content = article.get("content", "")[:500]
    return f"{title} {content}"


def _cluster_and_merge(articles: list[dict], sim_matrix, threshold: float) -> list[dict]:
    """Union-find clustering on similarity matrix, keep best source per cluster."""
    n = len(articles)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for i in range(n):
        for j in range(i + 1, n):
            if sim_matrix[i][j] >= threshold:
                union(i, j)

    # Group by cluster
    clusters: dict[int, list[int]] = {}
    for i in range(n):
        root = find(i)
        clusters.setdefault(root, []).append(i)

    # Keep the article with the longest content per cluster
    result = []
    for indices in clusters.values():
        best_idx = max(indices, key=lambda i: len(articles[i].get("content", "")))
        best = dict(articles[best_idx])

        cluster_titles = [articles[i]["title"] for i in indices if i != best_idx]
        best["corroboration_count"] = len(indices)
        best["merged_with"] = cluster_titles

        if cluster_titles:
            sources = [articles[i].get("source", "?") for i in indices]
            print(f"  [dedup] Merged cluster ({', '.join(sources)}): kept {best['source']}")

        result.append(best)

    return result


def _save_deduped(articles: list[dict]) -> Path:
    """Save deduplicated articles to JSON."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    json_path = OUTPUT_DIR / "deduped_deals.json"
    with open(json_path, "w") as f:
        json.dump(articles, f, indent=2)
    return json_path


def dedup_node(state: dict) -> dict:
    """LangGraph node: TF-IDF semantic deduplication."""
    articles = state.get("raw_articles", [])

    if len(articles) <= 1:
        deduplicated = articles
    else:
        texts = [_make_text(a) for a in articles]
        vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
        tfidf_matrix = vectorizer.fit_transform(texts)
        sim_matrix = cosine_similarity(tfidf_matrix)

        deduplicated = _cluster_and_merge(articles, sim_matrix, SIMILARITY_THRESHOLD_TFIDF)

    json_path = _save_deduped(deduplicated)

    metadata = {**state.get("metadata", {})}
    metadata["dedup_count"] = len(deduplicated)
    metadata["dedup_removed"] = len(articles) - len(deduplicated)
    metadata["dedup_method"] = "tfidf"

    print(f"  [dedup] {len(articles)} -> {len(deduplicated)} articles (removed {len(articles) - len(deduplicated)} duplicates)")

    return {
        "deduplicated_articles": deduplicated,
        "output_paths": {**state.get("output_paths", {}), "deduped_json": str(json_path)},
        "metadata": metadata,
    }
