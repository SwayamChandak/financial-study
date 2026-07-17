"""
Graph builder — assembles the daily study pipeline as a compiled LangGraph.

Pipeline (study):
  START → filter_by_memory → summarise_chunks
       → validate_summary
       → (valid → update_progress → END
          | retry → summarise_chunks
          | max_retries → update_progress → END)

Pipeline (chat):
  START → guardrail_node
       → (flagged → END | clean → rag_lookup_node)
       → (evidence_missing → END | has_evidence → validate_response_node)
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
from graph.nodes import (
    filter_by_memory,
    summarise_chunks,
    update_progress,
    validate_summary_node,
)
from graph.state import StudyState


def _decide_after_guardrail(state: StudyState) -> str:
    """Return ``"flagged"`` when the guardrail fired, else ``"clean"``."""
    return "flagged" if state.get("guardrail_flagged") else "clean"


def _decide_after_rag_lookup(state: StudyState) -> str:
    """Return ``"evidence_missing"`` when the evidence gate failed, else ``"has_evidence"``."""
    return "evidence_missing" if not state.get("evidence_found") else "has_evidence"


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


def _decide_after_summary_validation(state: StudyState) -> str:
    """
    Route after the summary validation node.

    - ``"valid"``        → the summary passed validation → update_progress
    - ``"max_retries"``  → retry count >= 3 → update_progress (accept what we have)
    - ``"retry"``        → failed validation, retries remain → summarise_chunks
    """
    if state.get("summary_validation_passed", False):
        return "valid"
    if state.get("summary_retry_count", 0) >= 3:
        return "max_retries"
    return "retry"


def build_study_graph() -> StateGraph:
    """
    Construct and compile the daily study workflow.

    The graph includes a validation loop: after summarising, the summary is
    checked for descriptiveness and length constraints. If it fails (up to 3
    retries), the graph loops back to the summarisation node.

    Returns a compiled LangGraph that can be invoked with an empty dict
    (all initial state is read from Redis / Qdrant inside the nodes).
    """
    builder = StateGraph(StudyState)

    builder.add_node("filter_by_memory", filter_by_memory)
    builder.add_node("summarise_chunks", summarise_chunks)
    builder.add_node("validate_summary", validate_summary_node)
    builder.add_node("update_progress", update_progress)

    builder.add_edge(START, "filter_by_memory")
    builder.add_edge("filter_by_memory", "summarise_chunks")
    builder.add_edge("summarise_chunks", "validate_summary")
    builder.add_conditional_edges(
        "validate_summary",
        _decide_after_summary_validation,
        {
            "valid": "update_progress",
            "retry": "summarise_chunks",
            "max_retries": "update_progress",
        },
    )
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
    builder.add_conditional_edges(
        "rag_lookup_node",
        _decide_after_rag_lookup,
        {"evidence_missing": END, "has_evidence": "validate_response_node"},
    )
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
