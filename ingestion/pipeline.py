"""
Ingestion pipeline orchestrator — runs the full load → chunk → embed → store flow.

Run this script once before the agent goes live, and re-run whenever new
study material is added or updated.

Usage:
    python -m ingestion.pipeline --source-dir data/raw
"""

from __future__ import annotations

import argparse

from config.settings import settings
from ingestion.chunker import chunk_documents
from ingestion.loader import load_documents
from ingestion.store import upsert_chunks


def run_pipeline(source_dir: str) -> None:
    """
    Execute the three-stage ingestion pipeline:

      Stage 1 — Load all PDFs from *source_dir* (one Document per page).
      Stage 2 — Truncate each PDF at its 'Comments' heading and split
                 the remaining text into overlapping chunks.
      Stage 3 — Embed chunks with all-MiniLM-L12-v2 and upsert into
                 the 'zerodha-varsity' Qdrant collection.
    """
    docs = load_documents(source_dir)
    chunks = chunk_documents(
        docs,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    upsert_chunks(chunks)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ingest Zerodha Varsity PDFs into the Qdrant vector store."
    )
    parser.add_argument(
        "--source-dir",
        required=True,
        help="Path to the directory containing module/chapter PDFs.",
    )
    args = parser.parse_args()
    run_pipeline(args.source_dir)
