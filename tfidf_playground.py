"""
TF-IDF Playground — step-by-step walkthrough of how TF-IDF vectorization,
cosine similarity, and deduplication work on the raw deals data.

Run:  python3 tfidf_playground.py
"""

import json
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ── Config ──────────────────────────────────────────────────────────────────
INPUT_FILE = "output/raw_deals.json"
CONTENT_PREVIEW_LEN = 500          # chars of content to use per article
SIMILARITY_THRESHOLD = 0.3         # pairs above this are flagged as similar
TOP_TERMS_PER_ARTICLE = 8          # how many top TF-IDF terms to show


def load_articles(path: str) -> list[dict]:
    with open(path) as f:
        return json.load(f)


def build_corpus(articles: list[dict]) -> list[str]:
    """Combine title + truncated content into a single string per article."""
    docs = []
    for a in articles:
        title = a.get("title", "")
        content = a.get("content", "")[:CONTENT_PREVIEW_LEN]
        docs.append(f"{title} {content}")
    return docs


def print_separator(title: str):
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def step1_show_raw_text(articles, corpus):
    print_separator("STEP 1 — Raw text being fed to TF-IDF")
    for i, (a, doc) in enumerate(zip(articles, corpus)):
        print(f"[{i}] {a['title'][:80]}")
        print(f"    source: {a.get('source', '?')}  |  id: {a.get('id', '?')}")
        print(f"    text length: {len(doc)} chars")
        print(f"    preview: {doc[:120]}...")
        print()


def step2_fit_tfidf(corpus):
    print_separator("STEP 2 — Fit TF-IDF vectorizer")

    vectorizer = TfidfVectorizer(
        stop_words="english",
        max_features=5000,
        ngram_range=(1, 2),
    )
    tfidf_matrix = vectorizer.fit_transform(corpus)
    feature_names = vectorizer.get_feature_names_out()

    print(f"Vocabulary size : {len(feature_names)}")
    print(f"TF-IDF matrix   : {tfidf_matrix.shape[0]} docs × {tfidf_matrix.shape[1]} features")
    print(f"Non-zero entries: {tfidf_matrix.nnz}  (sparsity: {1 - tfidf_matrix.nnz / (tfidf_matrix.shape[0] * tfidf_matrix.shape[1]):.2%})")
    print()

    # Top terms per document
    print("Top TF-IDF terms per article:")
    print("-" * 60)
    dense = tfidf_matrix.toarray()
    for i in range(len(corpus)):
        top_idx = dense[i].argsort()[::-1][:TOP_TERMS_PER_ARTICLE]
        terms = [(feature_names[j], dense[i][j]) for j in top_idx if dense[i][j] > 0]
        terms_str = ", ".join(f"{t}({w:.3f})" for t, w in terms)
        print(f"  [{i}] {terms_str}")
    print()

    return vectorizer, tfidf_matrix


def step3_cosine_similarity(tfidf_matrix, articles):
    print_separator("STEP 3 — Cosine similarity matrix")

    sim_matrix = cosine_similarity(tfidf_matrix)
    n = sim_matrix.shape[0]

    # Print header row
    hdr = "     " + "".join(f"[{i:>2}]  " for i in range(n))
    print(hdr)
    print("     " + "------" * n)
    for i in range(n):
        row = f"[{i:>2}] " + "  ".join(f"{sim_matrix[i][j]:.2f}" for j in range(n))
        print(row)
    print()

    return sim_matrix


def step4_similar_pairs(sim_matrix, articles):
    print_separator(f"STEP 4 — Similar pairs (threshold > {SIMILARITY_THRESHOLD})")

    n = sim_matrix.shape[0]
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            if sim_matrix[i][j] >= SIMILARITY_THRESHOLD:
                pairs.append((i, j, sim_matrix[i][j]))

    pairs.sort(key=lambda x: x[2], reverse=True)

    if not pairs:
        print("No pairs above threshold.")
    else:
        for i, j, score in pairs:
            print(f"  score={score:.3f}  [{i}] vs [{j}]")
            print(f"    A: {articles[i]['title'][:70]}")
            print(f"    B: {articles[j]['title'][:70]}")
            print()

    return pairs


def step5_cluster_and_dedup(sim_matrix, articles):
    print_separator("STEP 5 — Clustering & dedup result")

    n = sim_matrix.shape[0]
    visited = set()
    clusters = []

    for i in range(n):
        if i in visited:
            continue
        cluster = [i]
        visited.add(i)
        for j in range(i + 1, n):
            if j not in visited and sim_matrix[i][j] >= SIMILARITY_THRESHOLD:
                cluster.append(j)
                visited.add(j)
        clusters.append(cluster)

    kept = []
    for cluster in clusters:
        # Pick the article with the longest content as the "best" representative
        best = max(cluster, key=lambda idx: len(articles[idx].get("content", "")))
        kept.append(best)

        if len(cluster) == 1:
            print(f"  Cluster (unique): [{cluster[0]}] {articles[cluster[0]]['title'][:70]}")
        else:
            print(f"  Cluster (duplicates detected):")
            for idx in cluster:
                marker = " ✓ KEPT" if idx == best else "   dropped"
                print(f"    [{idx}]{marker} — {articles[idx]['title'][:65]}")
        print()

    print(f"Result: {len(articles)} articles → {len(kept)} after dedup "
          f"({len(articles) - len(kept)} removed)")


def main():
    print("TF-IDF Playground")
    print("=" * 80)
    print(f"Loading articles from: {INPUT_FILE}")

    articles = load_articles(INPUT_FILE)
    print(f"Loaded {len(articles)} articles\n")

    corpus = build_corpus(articles)

    step1_show_raw_text(articles, corpus)
    _, tfidf_matrix = step2_fit_tfidf(corpus)
    sim_matrix = step3_cosine_similarity(tfidf_matrix, articles)
    step4_similar_pairs(sim_matrix, articles)
    step5_cluster_and_dedup(sim_matrix, articles)


if __name__ == "__main__":
    main()
