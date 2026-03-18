"""FMCG Deal Intelligence Pipeline — Entry Point.

Usage:
    python main.py          # Live APIs (NewsAPI + RSS)
    python main.py --demo   # Use fallback dataset only
"""

import argparse
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from pipeline.graph import build_graph


def main():
    parser = argparse.ArgumentParser(description="FMCG Deal Intelligence Pipeline")
    parser.add_argument("--demo", action="store_true", help="Use fallback dataset instead of live APIs")
    args = parser.parse_args()

    print("FMCG Deal Intelligence Pipeline")
    print("=" * 40)

    graph = build_graph()
    result = graph.invoke({
        "raw_articles": [],
        "deduplicated_articles": [],
        "output_paths": {},
        "metadata": {
            "run_date": datetime.now().strftime("%Y-%m-%d"),
            "demo": args.demo,
        },
    })

    meta = result.get("metadata", {})
    paths = result.get("output_paths", {})

    print()
    print("Pipeline complete:")
    print(f"  Ingested:    {meta.get('ingested_count', '?')} articles ({', '.join(meta.get('sources_used', []))})")
    print(f"  URL dedup:   removed {meta.get('url_dedup_removed', '?')}")
    print(f"  TF-IDF dedup: {meta.get('dedup_count', '?')} unique (removed {meta.get('dedup_removed', '?')})")
    print()
    print("Output files:")
    for name, path in paths.items():
        print(f"  {name}: {path}")


if __name__ == "__main__":
    main()
