"""
Application settings — loaded from environment variables or a .env file.
"""

from __future__ import annotations

import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings for the studying agent.
    Overridable via environment variables or a .env file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM — Chatbot
    llm_chat_model_name: str = Field(default="ollama:llama3.2")

    # LLM — Study / summary
    llm_study_model_name: str = Field(default="ollama:llama3.2")

    llm_temperature: float = Field(default=0.2)
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="llama3.2")

    # Embeddings
    embedding_model_name: str = Field(
        default="sentence-transformers/all-MiniLM-L12-v2"
    )
    embedding_normalize: bool = Field(default=True)

    # Qdrant vector store
    qdrant_url: str = Field(default="http://localhost:6333")
    qdrant_collection: str = Field(default="zerodha-varsity")
    rag_top_k: int = Field(default=5)

    # Ingestion
    chunk_size: int = Field(default=600)
    chunk_overlap: int = Field(default=75)

    # LangSmith — tracing
    langsmith_tracing: bool = Field(default=True)
    langsmith_api_key: str = Field(default="")
    langsmith_project: str = Field(default="financial-study")

    # Redis — used for persistent progress memory
    redis_url: str = Field(default="redis://localhost:6379")

    # Quiz
    quiz_default_count: int = Field(default=10)
    quiz_cache_ttl: int = Field(default=3600)


def setup_langsmith() -> None:
    """Configure LangSmith tracing from application settings."""
    os.environ.setdefault("LANGSMITH_TRACING", str(settings.langsmith_tracing).lower())
    if settings.langsmith_api_key:
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    os.environ.setdefault("LANGSMITH_PROJECT", settings.langsmith_project)


settings = Settings()
