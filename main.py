"""FMCG Deal Intelligence Pipeline — Entry Point.

Usage:
    python main.py                  # Full pipeline (fetch + process)
    python main.py --demo           # Full pipeline with fallback dataset
    python main.py --skip-ingest    # Process existing raw_deals.json (dedup → score → newsletter)
    python main.py --skip-ingest --no-api   # Process with keyword scoring only
"""

import argparse
import json
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from config import OUTPUT_DIR
from pipeline.graph import build_full_graph, build_process_graph


def main():
    parser = argparse.ArgumentParser(description="FMCG Deal Intelligence Pipeline")
    parser.add_argument("--demo", action="store_true", help="Use fallback dataset instead of live APIs")
    parser.add_argument("--skip-ingest", action="store_true", help="Skip fetching — process existing raw_deals.json")
    parser.add_argument("--no-api", action="store_true", help="Disable LLM calls (keyword scoring only)")
    args = parser.parse_args()

    print("FMCG Deal Intelligence Pipeline")
    print("=" * 40)

    metadata = {
        "run_date": datetime.now().strftime("%Y-%m-%d"),
        "demo": args.demo,
        "no_api": args.demo or args.no_api,
    }

    if args.skip_ingest:
        # Load existing raw data and run processing only
        raw_path = OUTPUT_DIR / "raw_deals.json"
        print(f"  [skip-ingest] Loading {raw_path}")
        with open(raw_path) as f:
            raw_articles = json.load(f)
        print(f"  [skip-ingest] Loaded {len(raw_articles)} articles")

        graph = build_process_graph()
        result = graph.invoke({
            "raw_articles": raw_articles,
            "deduplicated_articles": [],
            "scored_articles": [],
            "newsletter_sections": {},
            "output_paths": {"raw_json": str(raw_path)},
            "metadata": {**metadata, "sources_used": ["existing"], "ingested_count": len(raw_articles)},
        })
    else:
        graph = build_full_graph()
        result = graph.invoke({
            "raw_articles": [],
            "deduplicated_articles": [],
            "scored_articles": [],
            "newsletter_sections": {},
            "output_paths": {},
            "metadata": metadata,
        })

    meta = result.get("metadata", {})
    paths = result.get("output_paths", {})

    print()
    print("Pipeline complete:")
    print(f"  Ingested:    {meta.get('ingested_count', '?')} articles ({', '.join(meta.get('sources_used', []))})")
    print(f"  TF-IDF dedup: {meta.get('dedup_count', '?')} unique (removed {meta.get('dedup_removed', '?')})")
    print(f"  Scoring:     {meta.get('scoring_method', '?')} — {meta.get('scored_count', '?')} above cutoff")
    print()
    print("Output files:")
    for name, path in paths.items():
        print(f"  {name}: {path}")

    from pipeline.cost_tracker import tracker as cost_tracker
    if cost_tracker.calls > 0:
        print()
        print(cost_tracker.summary())


if __name__ == "__main__":
    main()
