"""
Ingestion pipeline orchestrator — runs the full load → chunk → embed → store flow.

This is the single script to execute whenever study material is added or
updated.  It coordinates the other ingestion modules in order and logs
progress at each stage.

Usage:
    python -m ingestion.pipeline --source-dir data/raw

Planned functions / CLI:
  - run_pipeline(source_dir: str) -> None
      1. loader.load_documents(source_dir)   → raw Document list
      2. chunker.chunk_documents(docs)       → chunk Document list
      3. store.upsert_chunks(chunks)         → persists to vector DB
         (embedding is handled inside upsert_chunks via embedder)
      Logs counts at each step and raises on failure so CI/CD can catch it.

  - CLI entry point (if __name__ == "__main__")
      Parses --source-dir argument and calls run_pipeline().
"""
