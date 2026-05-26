"""
Ingestion pipeline package.

Run this pipeline once (and re-run whenever study material is added or
updated) to populate the vector DB before the agent goes live.

Execution order:
  loader   →   chunker   →   embedder   →   store

Entry point: ingestion.pipeline.run_pipeline()
"""
