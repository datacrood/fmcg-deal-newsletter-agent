"""LangGraph state schema for the FMCG deal pipeline."""

from __future__ import annotations

from typing import TypedDict


class PipelineState(TypedDict):
    raw_articles: list[dict]
    deduplicated_articles: list[dict]
    scored_articles: list[dict]
    newsletter_sections: dict
    output_paths: dict
    metadata: dict
