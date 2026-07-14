"""
Graph state — shared data passed between nodes in the study pipeline.

Study fields:
  current_module   — module number read from Redis at the start of each run
  current_chapter  — chapter number read from Redis at the start of each run
  chunks           — all Document chunks retrieved for the current chapter
  point_ids        — Qdrant point IDs matching each chunk (same order as chunks)
  total_chars      — sum of text_length across all retrieved chunks
  summary          — LLM-generated summary of the chapter content

Chatbot fields:
  want_new_information  — flag indicating the user wants fresh content (default False)
  already_asked         — flag indicating the user has already asked a question (default False)
  session_id            — unique identifier for the current chat session
  messages              — conversation history as LangChain message objects
  user_input            — the most recent user query / input
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
    want_new_information: bool
    already_asked: bool
    session_id: str
    messages: list[AnyMessage]
    user_input: str
    guardrail_flagged: bool
    chatbot_response: str
