"""Exploration script: spaCy entity extraction on raw_deals.json.

Run: python3 test/test_spacy_entities.py
"""

import json
from collections import Counter
from pathlib import Path

import spacy

DATA_PATH = Path(__file__).parent.parent / "output" / "raw_deals.json"

# ── Entity labels we care about ──
LABELS_OF_INTEREST = {"ORG", "MONEY", "PERSON", "GPE", "DATE", "PERCENT"}


def main():
    nlp = spacy.load("en_core_web_sm")

    with open(DATA_PATH) as f:
        articles = json.load(f)

    print(f"Loaded {len(articles)} articles\n")

    # ── Aggregate stats ──
    label_counts = Counter()
    label_examples: dict[str, list[str]] = {l: [] for l in LABELS_OF_INTEREST}

    # ── Process each article ──
    for i, art in enumerate(articles[:20]):  # first 20 to keep it fast
        title = art.get("title", "")
        content = art.get("content", "")[:3000]
        text = f"{title}\n{content}"

        doc = nlp(text)

        # Collect entities
        entities_by_label: dict[str, list[str]] = {}
        for ent in doc.ents:
            if ent.label_ in LABELS_OF_INTEREST:
                entities_by_label.setdefault(ent.label_, []).append(ent.text)
                label_counts[ent.label_] += 1
                if len(label_examples[ent.label_]) < 15:
                    label_examples[ent.label_].append(ent.text)

        # Print per-article summary
        print(f"{'='*80}")
        print(f"[{i}] {title[:80]}")
        print(f"    Source: {art.get('source', '?')}")
        for label in LABELS_OF_INTEREST:
            ents = entities_by_label.get(label, [])
            if ents:
                unique = list(dict.fromkeys(ents))  # dedupe preserving order
                print(f"    {label:8s}: {', '.join(unique[:8])}")

    # ── Summary ──
    print(f"\n{'='*80}")
    print("AGGREGATE STATS (first 20 articles)")
    print(f"{'='*80}")
    for label in sorted(label_counts, key=label_counts.get, reverse=True):
        unique_examples = list(dict.fromkeys(label_examples[label]))
        print(f"\n{label} ({label_counts[label]} total hits)")
        print(f"  Examples: {', '.join(unique_examples[:10])}")


if __name__ == "__main__":
    main()
