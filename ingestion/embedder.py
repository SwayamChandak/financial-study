"""
Embedder — converts text chunks into dense vector embeddings.

Responsibilities:
  - Load the configured embedding model (e.g. OpenAIEmbeddings,
    HuggingFaceEmbeddings) from config.settings
  - Accept a list of chunk Documents and produce their embeddings
  - Return embeddings paired with their source Documents so the store
    module can insert them together

Planned functions:
  - get_embedder() -> Embeddings
      Reads the embedding model name from settings and returns a
      ready-to-use LangChain Embeddings instance.

  - embed_chunks(chunks: list[Document]) -> list[tuple[Document, list[float]]]
      Calls the embedder in batches (respecting API rate limits) and
      returns (chunk, embedding_vector) pairs.
"""
