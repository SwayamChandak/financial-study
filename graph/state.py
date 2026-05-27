"""
Graph state — shared data passed between nodes in the study pipeline.

Fields:
  current_module   — module number read from Redis at the start of each run
  current_chapter  — chapter number read from Redis at the start of each run
  chunks           — all Document chunks retrieved for the current chapter
  point_ids        — Qdrant point IDs matching each chunk (same order as chunks)
  total_chars      — sum of text_length across all retrieved chunks
  summary          — LLM-generated summary of the chapter content
"""

from __future__ import annotations

from typing import Any

from langchain_core.documents import Document
from typing_extensions import TypedDict


class StudyState(TypedDict):
    current_module: int
    current_chapter: int
    chunks: list[Document]
    point_ids: list[Any]  # Qdrant point IDs (str or int UUIDs)
    total_chars: int
    summary: str
