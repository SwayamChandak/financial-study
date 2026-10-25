"""Tests for PDF loading and document chunking."""

from __future__ import annotations

from pathlib import Path

import pymupdf as fitz
from langchain_core.documents import Document

from ingestion.chunker import chunk_documents
from ingestion.loader import load_documents


def test_load_documents_extracts_pdf_metadata(tmp_path: Path) -> None:
    pdf_path = tmp_path / "chapter_3_test.pdf"
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 48), "5/27/26, 1:48 PM")  # pyright: ignore[reportUnknownMemberType]
    page.insert_text((72, 72), "Test Chapter")  # pyright: ignore[reportUnknownMemberType]
    page.insert_text((72, 100), "Module 2. Test Module")  # pyright: ignore[reportUnknownMemberType]
    page.insert_text((72, 128), "Chapter content for ingestion.")  # pyright: ignore[reportUnknownMemberType]
    pdf.save(pdf_path)  # pyright: ignore[reportUnknownMemberType]
    pdf.close()

    documents = load_documents(str(tmp_path))

    assert len(documents) == 1
    metadata = documents[0].metadata
    assert metadata["chapter_title"] == "Test Chapter"
    assert metadata["module_no"] == 2
    assert metadata["module_title"] == "Test Module"
    assert metadata["chapter_no"] == 3
    assert metadata["page_number"] == 1
    assert metadata["seen"] is False
    assert "Chapter content" in documents[0].page_content


def test_chunk_documents_removes_preamble_and_comments() -> None:
    document = Document(
        page_content=(
            "Table of contents\n1.1 Earlier chapter\n"
            "1. Chapter One\nBody text that should remain in the study material.\n"
            "Comments\nText that should not be ingested."
        ),
        metadata={"source_path": "chapter_1.pdf", "chapter_no": 1},
    )

    chunks = chunk_documents([document], chunk_size=40, chunk_overlap=5)

    combined_text = "\n".join(chunk.page_content for chunk in chunks)
    assert chunks
    assert "Table of contents" not in combined_text
    assert "Comments" not in combined_text
    assert "should not be ingested" not in combined_text
    assert "Body text" in combined_text
    assert [chunk.metadata["chunk_index"] for chunk in chunks] == list(
        range(len(chunks))
    )
    assert chunks[0].metadata["chapter_title"] == "Chapter One"
