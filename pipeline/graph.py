"""LangGraph graph definition: ingest -> dedup -> END."""

from langgraph.graph import END, START, StateGraph

from pipeline.state import PipelineState
from pipeline.ingest import ingest_node
from pipeline.dedup import dedup_node


def build_graph() -> StateGraph:
    """Build and compile the LangGraph pipeline."""
    graph = StateGraph(PipelineState)

    graph.add_node("ingest", ingest_node)
    graph.add_node("dedup", dedup_node)

    graph.add_edge(START, "ingest")
    graph.add_edge("ingest", "dedup")
    graph.add_edge("dedup", END)

    return graph.compile()
