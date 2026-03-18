"""LangGraph graph definitions.

Two graphs:
  build_full_graph()    — ingest → dedup → score → newsletter (end-to-end)
  build_process_graph() — dedup → score → newsletter (assumes raw_articles loaded)
"""

from langgraph.graph import END, START, StateGraph

from pipeline.state import PipelineState
from pipeline.ingest import ingest_node
from pipeline.dedup import dedup_node
from pipeline.scorer import score_node
from pipeline.newsletter import newsletter_node


def build_full_graph():
    """Full pipeline: ingest → dedup → score → newsletter."""
    graph = StateGraph(PipelineState)

    graph.add_node("ingest", ingest_node)
    graph.add_node("dedup", dedup_node)
    graph.add_node("score", score_node)
    graph.add_node("newsletter", newsletter_node)

    graph.add_edge(START, "ingest")
    graph.add_edge("ingest", "dedup")
    graph.add_edge("dedup", "score")
    graph.add_edge("score", "newsletter")
    graph.add_edge("newsletter", END)

    return graph.compile()


def build_process_graph():
    """Processing only: dedup → score → newsletter (raw_articles already loaded)."""
    graph = StateGraph(PipelineState)

    graph.add_node("dedup", dedup_node)
    graph.add_node("score", score_node)
    graph.add_node("newsletter", newsletter_node)

    graph.add_edge(START, "dedup")
    graph.add_edge("dedup", "score")
    graph.add_edge("score", "newsletter")
    graph.add_edge("newsletter", END)

    return graph.compile()
