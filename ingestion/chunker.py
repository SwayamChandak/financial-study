"""
Document chunker — strips the 'Comments' section then splits into chunks.

Processing per PDF (pages grouped by source_path):

  1. Iterate pages in reading order.
  2. On each page, search for a 'Comments' heading using regex.
  3. If found, keep only the text *before* the heading; mark the
     current PDF as finished — all subsequent pages are discarded.
  4. Collect the surviving page texts and split them with
     RecursiveCharacterTextSplitter, preserving all source metadata.

Metadata added by this module (on top of what loader.py attaches):
  chunk_index  int  — 0-based position of this chunk within its chapter
  text_length  int  — character count of the chunk's final text
"""

from __future__ import annotations

import re
from itertools import groupby

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


# Matches lines like "Comments", "1,279  comments", "100 Comment" —
# an optional leading number (with commas) followed by the word comments.
_COMMENTS_RE = re.compile(r"(?m)^\s*(?:\d[\d,]*\s+)?[Cc]omments?\s*$")


def _truncate_at_comments(text: str) -> tuple[str, bool]:
    """
    Return (truncated_text, comments_was_found).

    If a 'Comments' heading is found, *truncated_text* is everything before
    that heading and *comments_was_found* is True.  Otherwise the original
    text is returned unchanged and *comments_was_found* is False.
    """
    match = _COMMENTS_RE.search(text)
    if match:
        return text[: match.start()], True
    return text, False


def chunk_documents(
    documents: list[Document],
    chunk_size: int = 500,
    chunk_overlap: int = 75,
) -> list[Document]:
    """
    Truncate each PDF at its first 'Comments' heading then split the
    remaining content into overlapping text chunks.

    Args:
      documents:     Flat list of page-level Documents from the loader.
      chunk_size:    Maximum character length of each output chunk.
      chunk_overlap: Number of characters shared between adjacent chunks.

    Returns:
      Flat list of chunk Documents.  Each chunk carries the full metadata
      schema from loader.py plus:
        chunk_index  (int) — 0-based position within its chapter
        text_length  (int) — character count of the chunk text
    """
    # Sort by (source_path, page_number) so pages arrive in reading order.
    sorted_docs = sorted(
        documents,
        key=lambda d: (
            d.metadata.get("source_path", ""),
            d.metadata.get("page_number", 0),
        ),
    )

    filtered: list[Document] = []
    for _src, page_iter in groupby(sorted_docs, key=lambda d: d.metadata.get("source_path", "")):
        comments_encountered = False
        for doc in page_iter:
            if comments_encountered:
                continue

            truncated, found = _truncate_at_comments(doc.page_content)
            if found:
                comments_encountered = True

            if truncated.strip():
                filtered.append(Document(page_content=truncated, metadata=doc.metadata))

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ".", " ", ""],
    )
    raw_chunks = splitter.split_documents(filtered)

    # Group by chapter (source_path) to assign per-chapter chunk_index.
    raw_chunks.sort(key=lambda d: d.metadata.get("source_path", ""))
    final_chunks: list[Document] = []
    for _src, chunk_iter in groupby(raw_chunks, key=lambda d: d.metadata.get("source_path", "")):
        for idx, chunk in enumerate(chunk_iter):
            chunk.metadata["chunk_index"] = idx
            chunk.metadata["text_length"] = len(chunk.page_content)
            final_chunks.append(chunk)

    return final_chunks
