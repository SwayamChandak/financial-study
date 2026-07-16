"""
Document chunker — strips preamble, strips the 'Comments' section,
then splits into chunks.

Processing per PDF (pages grouped by source_path):

  1. Iterate pages in reading order.
  2. For each PDF, find the chapter heading line
     "{chapterNo}. {ChapterName}" and discard everything before it
     (table-of-contents / navigation preamble).
  3. On each subsequent page, search for a 'Comments' heading using
     regex; keep only the text *before* it.
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


def _strip_preamble(pages: list[Document]) -> list[Document]:
    """
    For a single PDF's pages, find the heading line

      {chapterNo}. {ChapterName}

    and discard everything before it.  The pattern is *not* mistaken for
    table-of-contents lines like "{chapterNo}. {chapterNo} {ChapterName}".

    Updates *chapter_title* metadata with the extracted chapter name.
    """
    if not pages:
        return pages

    chapter_no = pages[0].metadata.get("chapter_no", 0)
    if not chapter_no:
        return pages

    # Matches e.g. "1. Background" but NOT "1. 1 Background".
    heading_re = re.compile(
        rf"^({chapter_no})\.\s+(?!\1\b)(.+)$", re.MULTILINE,
    )

    result: list[Document] = []
    heading_found = False

    for doc in pages:
        if heading_found:
            result.append(doc)
            continue

        match = heading_re.search(doc.page_content)
        if match:
            heading_found = True
            doc.metadata["chapter_title"] = match.group(2).strip()
            trimmed = doc.page_content[match.start() :]
            if trimmed.strip():
                result.append(Document(page_content=trimmed, metadata=doc.metadata))

    return result


def chunk_documents(
    documents: list[Document],
    chunk_size: int = 500,
    chunk_overlap: int = 75,
) -> list[Document]:
    """
    Strip preamble & Comments section, then split into overlapping chunks.

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
        pages = list(page_iter)

        # Step 1 — discard preamble before "{chapterNo}. {ChapterName}"
        pages = _strip_preamble(pages)

        # Step 2 — truncate at the "Comments" heading
        comments_encountered = False
        for doc in pages:
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
