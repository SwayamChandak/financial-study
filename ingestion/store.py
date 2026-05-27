"""
Vector store — persists embedded chunks into Qdrant and exposes a retriever.

Collection : zerodha-varsity  (configurable via settings.qdrant_collection)
Backend    : Qdrant running locally at http://localhost:6333
Distance   : Cosine (matches L2-normalized all-MiniLM-L12-v2 embeddings)
"""

from __future__ import annotations

from typing import Any

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    VectorParams,
)

from config.settings import settings
from ingestion.embedder import get_embedder

# Output dimension of sentence-transformers/all-MiniLM-L12-v2.
_EMBEDDING_DIM = 384


def _get_client() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url)


def get_vector_store() -> QdrantVectorStore:
    """
    Connect to the Qdrant instance and return a QdrantVectorStore.
    Creates the collection with cosine distance if it does not exist yet.
    """
    client = _get_client()

    if not client.collection_exists(settings.qdrant_collection):
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(size=_EMBEDDING_DIM, distance=Distance.COSINE),
        )

    return QdrantVectorStore(
        client=client,
        collection_name=settings.qdrant_collection,
        embedding=get_embedder(),
    )


def upsert_chunks(chunks: list[Document]) -> None:
    """
    Embed *chunks* with all-MiniLM-L12-v2 and upsert them into Qdrant.

    All source metadata (module_number, chapter_number, source_path) is
    stored alongside each vector and is available for filtered retrieval.
    """
    get_vector_store().add_documents(chunks)


def get_retriever(
    module_number: int | None = None,
    chapter_number: int | None = None,
    top_k: int | None = None,
) -> BaseRetriever:
    """
    Return a LangChain retriever backed by Qdrant.

    Args:
      module_number:  If provided, restricts results to this module.
      chapter_number: If provided, restricts results to this chapter.
      top_k:          Number of passages to return (default: settings.rag_top_k).

    Returns:
      A retriever usable directly in LangChain / LangGraph chains.
    """
    k = top_k if top_k is not None else settings.rag_top_k

    conditions: list[FieldCondition] = []
    if module_number is not None:
        conditions.append(
            FieldCondition(
                key="metadata.module_number",
                match=MatchValue(value=module_number),
            )
        )
    if chapter_number is not None:
        conditions.append(
            FieldCondition(
                key="metadata.chapter_number",
                match=MatchValue(value=chapter_number),
            )
        )

    search_kwargs: dict = {"k": k}
    if conditions:
        search_kwargs["filter"] = Filter(must=conditions)

    return get_vector_store().as_retriever(search_kwargs=search_kwargs)


def fetch_all_chunks(
    module_no: int,
    chapter_no: int,
) -> tuple[list[Document], list[Any]]:
    """
    Return *all* stored chunks for the given module and chapter.

    Unlike get_retriever (which uses semantic similarity and a top-k limit),
    this function scrolls through the entire Qdrant collection and returns
    every point whose metadata matches the given module_no and chapter_no.

    Args:
      module_no:   Module number to filter on (``metadata.module_no``).
      chapter_no:  Chapter number to filter on (``metadata.chapter_no``).

    Returns:
      A tuple of (documents, point_ids) where:
        documents  — list of Document objects reconstructed from Qdrant payloads
        point_ids  — Qdrant point IDs in the same order as documents
    """
    client = _get_client()
    scroll_filter = Filter(
        must=[
            FieldCondition(key="metadata.module_no", match=MatchValue(value=module_no)),
            FieldCondition(key="metadata.chapter_no", match=MatchValue(value=chapter_no)),
        ]
    )

    documents: list[Document] = []
    point_ids: list[Any] = []
    offset = None

    while True:
        records, next_offset = client.scroll(
            collection_name=settings.qdrant_collection,
            scroll_filter=scroll_filter,
            with_payload=True,
            with_vectors=False,
            limit=100,
            offset=offset,
        )
        for record in records:
            payload = record.payload or {}
            doc = Document(
                page_content=payload.get("page_content", ""),
                metadata=payload.get("metadata", {}),
            )
            documents.append(doc)
            point_ids.append(record.id)

        if next_offset is None:
            break
        offset = next_offset

    return documents, point_ids


def mark_chunks_seen(
    point_ids: list[Any],
    chunks: list[Document],
) -> None:
    """
    Set ``seen = True`` in the Qdrant payload for each supplied point.

    The full metadata dict is reconstructed for each point (to avoid
    overwriting other metadata fields) with ``seen`` set to ``True``,
    and then written back via ``set_payload``.

    Args:
      point_ids: Qdrant point IDs returned by ``fetch_all_chunks``.
      chunks:    Documents in the same order as *point_ids*.
    """
    client = _get_client()
    for point_id, chunk in zip(point_ids, chunks):
        updated_metadata = {**chunk.metadata, "seen": True}
        client.set_payload(
            collection_name=settings.qdrant_collection,
            payload={"metadata": updated_metadata},
            points=[point_id],
        )
