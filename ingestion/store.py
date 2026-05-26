"""
Vector store — persists embedded chunks into the vector DB.

Responsibilities:
  - Connect to the configured vector DB backend (e.g. Chroma, Pinecone,
    Qdrant) using RAGSettings from config.settings
  - Upsert (chunk, embedding) pairs into the correct collection
  - Store chunk metadata (module_number, chapter_number, source_path)
    alongside each vector so downstream retrieval can filter by them
  - Expose a retriever factory used by both agent workflows at runtime

Planned functions:
  - get_vector_store() -> VectorStore
      Returns a connected VectorStore instance using settings.

  - upsert_chunks(chunks: list[Document]) -> None
      Embeds and upserts a batch of chunks; idempotent on re-run
      (deduplicates by source_path + chunk index).

  - get_retriever(
        module_number:  int | None = None,
        chapter_number: int | None = None,
        top_k:          int        = settings.rag.top_k,
    ) -> BaseRetriever
      Returns a retriever optionally filtered to a specific module /
      chapter; used by both the daily-article and chatbot workflows.
"""
