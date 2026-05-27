"""
Document loader — reads PDF study material from disk.

Metadata is extracted from PDF *content*, not filenames:

  chapter_title  — topmost non-numeric text on the first page (the running
                   header that Zerodha Varsity repeats on every page)
  module_no      — parsed from "Module 1. Introduction to Stock Markets"
  module_title   — the text after "Module N." on the same line
  chapter_no     — parsed from filename as a fallback (e.g. chapter_3_...)
  article_link   — https://zerodha.com/varsity/chapter/<chapter-title-slug>/
  source_path    — absolute path of the originating PDF
  page_number    — 1-based PDF page number
  ingested_at    — ISO 8601 UTC ingestion run

Fields added later by chunker.py:
  chunk_index    — 0-based position of this chunk within the chapter
  text_length    — character count of the final chunk text
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import fitz  # PyMuPDF — used directly for structured text extraction
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_core.documents import Document


# ── Regex patterns ────────────────────────────────────────────────────────────

# Matches: "Module 1. Introduction to Stock Markets"
_MODULE_RE = re.compile(r"Module\s+(\d+)\.\s+(.+?)(?:\n|$)", re.IGNORECASE)

# Fallback: chapter number from filename (e.g. "chapter_3_", "ch3_")
_CHAPTER_NO_RE = re.compile(r"(?:chapter|ch)[_\s-]?(\d+)", re.IGNORECASE)

_VARSITY_BASE = "https://zerodha.com/varsity/chapter/"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _to_slug(title: str) -> str:
    """'The Need to Invest' → 'the-need-to-invest'"""
    return re.sub(r"\s+", "-", title.strip().lower())


# Matches a timestamp like "5/27/26, 1:48 PM" anywhere in a text block.
_TIMESTAMP_RE = re.compile(
    r"\d{1,2}/\d{1,2}/\d{2,4},?\s+\d{1,2}:\d{2}\s*[APap][Mm]",
)


def _extract_header_text(page: fitz.Page) -> str:
    """
    Return the chapter title from the topmost text block on *page*.

    The header block contains a timestamp followed by the chapter title, e.g.:
        "5/27/26, 1:48 PM\nWhy should you invest: Understanding the need to invest"

    Strategy:
      - Search the block text for a timestamp (date + HH:MM AM/PM).
      - Split at the end of the timestamp; take everything after it as the title.
      - If no timestamp is found, fall back to the first non-numeric line.
    """
    blocks = page.get_text("blocks")
    # Each block tuple: (x0, y0, x1, y1, text, block_no, block_type)
    text_blocks = sorted(
        [(b[1], b[4].strip()) for b in blocks if b[6] == 0 and b[4].strip()],
        key=lambda x: x[0],  # ascending by y0
    )
    for _, text in text_blocks:
        ts_match = _TIMESTAMP_RE.search(text)
        if ts_match:
            # Everything after the timestamp is the chapter title.
            after = text[ts_match.end() :].strip()
            # Take only the first line in case of trailing noise.
            title = after.split("\n")[0].strip()
            if title and not re.match(r"^\d+$", title):
                return title
        else:
            # No timestamp — use the first non-numeric line as-is.
            first_line = text.split("\n")[0].strip()
            if first_line and not re.match(r"^\d+$", first_line):
                return first_line
    return ""


def _extract_pdf_metadata(pdf_path: Path) -> dict:
    """
    Open *pdf_path* with PyMuPDF and return the full base metadata dict.

    Extracts:
      - chapter_title  : topmost header text from the first page
      - module_no      : from "Module N. Title" in the first 3 pages
      - module_title   : the title part of the same pattern
      - chapter_no     : from filename stem (fallback)
      - article_link   : Varsity URL built from chapter_title slug
      - source_path    : absolute path string
    """
    module_no = 0
    module_title = ""
    chapter_no = 0
    chapter_title = ""

    with fitz.open(str(pdf_path)) as doc:
        if len(doc) > 0:
            chapter_title = _extract_header_text(doc[0])

        # Search the first 3 pages for the "Module N. Title" line
        for i in range(min(3, len(doc))):
            text = doc[i].get_text()
            m = _MODULE_RE.search(text)
            if m:
                module_no = int(m.group(1))
                module_title = m.group(2).strip()
                break

    # Fallback: chapter number from filename
    c = _CHAPTER_NO_RE.search(pdf_path.stem)
    if c:
        chapter_no = int(c.group(1))

    article_link = f"{_VARSITY_BASE}{_to_slug(chapter_title)}/" if chapter_title else ""

    return {
        "source_path": str(pdf_path),
        "article_link": article_link,
        "module_no": module_no,
        "module_title": module_title,
        "chapter_no": chapter_no,
        "chapter_title": chapter_title,
    }


def load_documents(source_dir: str) -> list[Document]:
    """
    Recursively walk *source_dir*, load every PDF with PyMuPDF (one
    Document per page), and attach the full metadata schema to each page.

    Raises:
      FileNotFoundError — if *source_dir* does not exist.
      ValueError        — if no PDF files are found inside it.
    """
    root = Path(source_dir)
    if not root.exists():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")

    pdf_files = sorted(root.rglob("*.pdf"))
    if not pdf_files:
        raise ValueError(f"No PDF files found in: {source_dir}")

    ingested_at = datetime.now(timezone.utc).isoformat()

    all_docs: list[Document] = []
    for pdf_path in pdf_files:
        base_meta = _extract_pdf_metadata(pdf_path)
        pages: list[Document] = PyMuPDFLoader(str(pdf_path)).load()
        for page in pages:
            page.metadata.update(
                {
                    **base_meta,
                    "page_number": page.metadata.get("page", 0) + 1,
                    "ingested_at": ingested_at,
                }
            )
        all_docs.extend(pages)

    return all_docs
