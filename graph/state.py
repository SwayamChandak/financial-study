"""
Graph state — shared data passed between nodes in the study and chatbot pipelines.
"""

from __future__ import annotations

from typing import Any

from langchain_core.documents import Document
from langchain_core.messages import AnyMessage
from typing_extensions import TypedDict


class StudyState(TypedDict):
    # Study pipeline
    current_module: int
    current_chapter: int
    chunks: list[Document]
    point_ids: list[Any]  # Qdrant point IDs (str or int UUIDs)
    total_chars: int
    summary: str

    # Chatbot
    messages: list[AnyMessage]
    user_input: str
    guardrail_flagged: bool
    chatbot_response: str
    validation_passed: bool
    rag_retry_count: int
    rag_search_query: str
    evidence_found: bool
    memory_context: str

    # Study summary validation
    summary_retry_count: int
    summary_validation_passed: bool
