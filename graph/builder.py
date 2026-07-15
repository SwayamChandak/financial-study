"""
Graph builder — assembles the daily study pipeline as a compiled LangGraph.

Pipeline (study):
  START → filter_by_memory → summarise_chunks → update_progress → END

Pipeline (chat):
  START → guardrail_node
       → (flagged → END | clean → rag_lookup_node)
       → validate_response_node
       → (valid → END | retry → rag_lookup_node | max_retries → END)

Usage:
    from graph.builder import build_study_graph, build_chat_graph

    study_graph = build_study_graph()
    study_graph.invoke({})

    chat_graph = build_chat_graph()
    chat_graph.invoke({"user_input": "What is Nifty?"})
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from graph.chat_nodes import (
    guardrail_node,
    rag_lookup_node,
    validate_response_node,
)
from graph.nodes import filter_by_memory, summarise_chunks, update_progress
from graph.state import StudyState


def _decide_after_guardrail(state: StudyState) -> str:
    """Return ``"flagged"`` when the guardrail fired, else ``"clean"``."""
    return "flagged" if state.get("guardrail_flagged") else "clean"


def _decide_after_validation(state: StudyState) -> str:
    """
    Route after the validation node.

    - ``"valid"``        → the answer passed validation → END
    - ``"max_retries"``  → retry count >= 3 → END
    - ``"retry"``        → failed validation, retries remain → rag_lookup_node
    """
    if state.get("validation_passed", False):
        return "valid"
    if state.get("rag_retry_count", 0) >= 3:
        return "max_retries"
    return "retry"


def build_study_graph() -> StateGraph:
    """
    Construct and compile the daily study workflow.

    Returns a compiled LangGraph that can be invoked with an empty dict
    (all initial state is read from Redis / Qdrant inside the nodes).
    """
    builder = StateGraph(StudyState)

    builder.add_node("filter_by_memory", filter_by_memory)
    builder.add_node("summarise_chunks", summarise_chunks)
    builder.add_node("update_progress", update_progress)

    builder.add_edge(START, "filter_by_memory")
    builder.add_edge("filter_by_memory", "summarise_chunks")
    builder.add_edge("summarise_chunks", "update_progress")
    builder.add_edge("update_progress", END)

    return builder.compile()


def build_chat_graph() -> StateGraph:
    """
    Construct and compile the chatbot workflow.

    The graph expects at minimum ``state["user_input"]`` to be set.
    Returns a compiled LangGraph that can be invoked with:

        graph.invoke({"user_input": "What is the stock market?"})
    """
    builder = StateGraph(StudyState)

    builder.add_node("guardrail_node", guardrail_node)
    builder.add_node("rag_lookup_node", rag_lookup_node)
    builder.add_node("validate_response_node", validate_response_node)

    builder.add_edge(START, "guardrail_node")
    builder.add_conditional_edges(
        "guardrail_node",
        _decide_after_guardrail,
        {"flagged": END, "clean": "rag_lookup_node"},
    )
    builder.add_edge("rag_lookup_node", "validate_response_node")
    builder.add_conditional_edges(
        "validate_response_node",
        _decide_after_validation,
        {
            "valid": END,
            "retry": "rag_lookup_node",
            "max_retries": END,
        },
    )

    return builder.compile()


if __name__ == "__main__":
    graph = build_study_graph()
    graph.invoke({})
