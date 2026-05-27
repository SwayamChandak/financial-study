"""
Vector store — persists embedded chunks into Qdrant and exposes a retriever.

Collection : zerodha-varsity  (configurable via settings.qdrant_collection)
Backend    : Qdrant running locally at http://localhost:6333
Distance   : Cosine (matches L2-normalized all-MiniLM-L12-v2 embeddings)
"""

from __future__ import annotations

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
