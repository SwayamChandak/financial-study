"""
Application settings — loaded from environment variables or a .env file.

All fields can be overridden via environment variables or a .env file.
Environment variable names match the field names (case-insensitive).

Example .env:
    EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L12-v2
    QDRANT_URL=http://localhost:6333
    TELEGRAM_BOT_TOKEN=your-token-here
    REDIS_URL=redis://localhost:6379
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings for the studying agent.

    All fields can be overridden via environment variables or a .env file.
    Environment variable names match the field names (case-insensitive).

    Example .env:
        EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L12-v2
        QDRANT_URL=http://localhost:6333
        TELEGRAM_BOT_TOKEN=your-token-here
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    llm_model_name: str = Field(default="azure_openai:gpt-4")
    llm_temperature: float = Field(default=0.2)
    llm_max_tokens: int = Field(default=2048)

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

    # Telegram
    telegram_bot_token: str = Field(default="")
    telegram_allowed_chat_ids: list[int] = Field(default_factory=list)

    # Scheduler
    scheduler_cron: str = Field(default="0 8 * * *")
    scheduler_timezone: str = Field(default="Asia/Kolkata")

    # Graph
    graph_recursion_limit: int = Field(default=25)

    # Redis — used for persistent progress memory (last_module_no, last_chapter_no)
    redis_url: str = Field(default="redis://localhost:6740")


settings = Settings()
