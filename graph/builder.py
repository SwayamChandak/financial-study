"""
Graph builder — assembles the daily study pipeline as a compiled LangGraph.

Pipeline:
  START → filter_by_memory → summarise_chunks → update_progress → END

Usage:
    from graph.builder import build_study_graph

    graph = build_study_graph()
    graph.invoke({})
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from graph.nodes import filter_by_memory, summarise_chunks, update_progress
from graph.state import StudyState


def build_study_graph() -> StateGraph:
    """
    Construct and compile the daily study workflow.

    Returns a compiled LangGraph that can be invoked with an empty dict
    (all initial state is read from Redis / Qdrant inside the nodes).
    """
    builder = StateGraph(StudyState)

    # Register nodes
    builder.add_node("filter_by_memory", filter_by_memory)
    builder.add_node("summarise_chunks", summarise_chunks)
    builder.add_node("update_progress", update_progress)

    # Connect edges
    builder.add_edge(START, "filter_by_memory")
    builder.add_edge("filter_by_memory", "summarise_chunks")
    builder.add_edge("summarise_chunks", "update_progress")
    builder.add_edge("update_progress", END)

    return builder.compile()

if __name__ == "__main__":
    graph = build_study_graph()
    graph.invoke({})