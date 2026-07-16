"""
Ingestion pipeline orchestrator — runs the full load → chunk → embed → store flow.

Run this script once before the agent goes live, and re-run whenever new
study material is added or updated.

Usage:
    python -m ingestion.pipeline --source-dir data/raw
"""

from __future__ import annotations

import argparse
import re
from itertools import groupby
from pathlib import Path

from langchain_core.documents import Document

from config.settings import settings
from ingestion.chunker import chunk_documents
from ingestion.loader import load_documents
from ingestion.store import upsert_chunks


def _write_chunks_md(chunks: list[Document], output_dir: str = "data/md") -> None:
    """Group chunks by source_path and write one markdown file per PDF."""
    sorted_chunks = sorted(chunks, key=lambda d: d.metadata.get("source_path", ""))
    out_root = Path(output_dir)

    for src, chunk_iter in groupby(sorted_chunks, key=lambda d: d.metadata.get("source_path", "")):
        chunk_list = list(chunk_iter)
        meta = chunk_list[0].metadata
        module_no = meta.get("module_no", 0)
        module_title = meta.get("module_title", "")
        chapter_no = meta.get("chapter_no", 0)
        chapter_title = meta.get("chapter_title", "")

        module_dir = out_root / f"module_{module_no}"
        module_dir.mkdir(parents=True, exist_ok=True)

        safe = re.sub(r'[\\/:*?"<>|]', "_", chapter_title) if chapter_title else f"chapter_{chapter_no}"
        md_path = module_dir / f"{safe}.md"

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"# {chapter_title}\n\n")
            if module_no:
                f.write(f"**Module {module_no}:** {module_title}\n\n")
            f.write("---\n\n")
            for chunk in chunk_list:
                idx = chunk.metadata.get("chunk_index", 0)
                # Use a subtle HTML comment for chunk index so it's invisible
                # when rendered but still traceable.
                f.write(f"<!-- chunk {idx} -->\n\n{chunk.page_content}\n\n---\n\n")


def run_pipeline(source_dir: str) -> None:
    """
    Execute the full ingestion pipeline:

      Stage 1 — Load all PDFs from *source_dir* (one Document per page).
      Stage 2 — Truncate each PDF at its 'Comments' heading and split
                 the remaining text into overlapping chunks.
      Stage 3 — Write one markdown file per PDF with the chunked content.
      Stage 4 — Embed chunks with all-MiniLM-L12-v2 and upsert into
                 the 'zerodha-varsity' Qdrant collection.
    """
    docs = load_documents(source_dir)
    chunks = chunk_documents(
        docs,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    _write_chunks_md(chunks)
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
