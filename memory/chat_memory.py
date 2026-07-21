"""
Chat memory — persists conversation history in Redis for the chatbot.

Key stored in Redis:
  chat:memory  — Redis LIST of JSON-encoded {timestamp, question, answer} objects

Behaviours:
  - TTL of 30 days on the key to prevent unlimited growth
  - Automatic summarisation of older entries when the list exceeds 15 messages
  - Summary sent as long-term memory; recent entries sent as medium-term memory
  - Graceful degradation when Redis is unavailable (logs warning, no crash)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

import redis

from config.settings import settings

logger = logging.getLogger(__name__)

MEMORY_KEY = "chat:memory"
MAX_MESSAGES_BEFORE_SUMMARY = 15
KEEP_ON_SUMMARY = 10
TTL_SECONDS = 30 * 24 * 60 * 60


class MemoryService:
    """Redis-backed conversation memory for the chatbot.

    Provides append, retrieval, clear, and automatic summarisation when
    the conversation history grows too large.
    """

    def __init__(self, redis_url: Optional[str] = None) -> None:
        self._redis_url = redis_url or settings.redis_url
        self._redis: Optional[redis.Redis] = None
        self._connect()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _connect(self) -> None:
        """Establish a Redis connection and verify it with a PING."""
        try:
            self._redis = redis.from_url(self._redis_url, decode_responses=True)
            self._redis.ping()
        except redis.RedisError as exc:
            logger.warning("Redis connection failed (%s) — memory will not be persisted", exc)
            self._redis = None

    def _get_client(self) -> Optional[redis.Redis]:
        """Return the Redis client, attempting a reconnection if it is ``None``."""
        if self._redis is None:
            try:
                self._connect()
            except redis.RedisError:
                pass
        return self._redis

    def _ensure_connection(func):  # noqa: N805
        """Decorator that calls ``_get_client`` and passes the client as the first argument.

        If Redis is unavailable the wrapped function receives ``None`` and can
        decide how to degrade gracefully.
        """

        def wrapper(self, *args, **kwargs):
            client = self._get_client()
            return func(self, client, *args, **kwargs)

        return wrapper

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    @staticmethod
    def _serialize_entry(question: str, answer: str) -> str:
        return json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "question": question,
                "answer": answer,
            },
            ensure_ascii=False,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @_ensure_connection
    def add_to_memory(self, client: Optional[redis.Redis], question: str, answer: str) -> None:
        """Append a question/answer pair to the conversation history.

        Args:
            client: Redis client (or ``None`` if unavailable).
            question: The user's question.
            answer: The bot's response.
        """
        if client is None:
            logger.debug("Redis unavailable — skipping add_to_memory")
            return

        try:
            entry = self._serialize_entry(question, answer)
            pipe = client.pipeline()
            pipe.lpush(MEMORY_KEY, entry)
            pipe.expire(MEMORY_KEY, TTL_SECONDS)
            pipe.execute()

            length = client.llen(MEMORY_KEY)
            if length > MAX_MESSAGES_BEFORE_SUMMARY:
                self._summarize_memory(client)
        except redis.RedisError as exc:
            logger.error("Failed to add entry to memory: %s", exc)

    @_ensure_connection
    def get_recent_memory(self, client: Optional[redis.Redis], limit: int = 10) -> list[dict]:  # noqa: C901
        """Return the *limit* most recent conversation turns.

        Results are returned oldest-first (chronological order).

        Args:
            client: Redis client (or ``None`` if unavailable).
            limit: Maximum number of entries to retrieve (default 10).

        Returns:
            List of dicts with keys ``timestamp``, ``question``, ``answer``.
        """
        if client is None:
            logger.debug("Redis unavailable — returning empty memory")
            return []

        try:
            raw_entries = client.lrange(MEMORY_KEY, 0, limit - 1)
        except redis.RedisError as exc:
            logger.error("Failed to retrieve memory: %s", exc)
            return []

        entries: list[dict] = []
        for raw in raw_entries:
            try:
                entry = json.loads(raw)
                if all(k in entry for k in ("timestamp", "question", "answer")):
                    entries.append(entry)
                else:
                    logger.warning("Skipping malformed memory entry: %s", raw[:120])
            except (json.JSONDecodeError, TypeError) as exc:
                logger.warning("Skipping unparseable memory entry (%s): %s", exc, raw[:120])

        return entries

    @_ensure_connection
    def clear_memory(self, client: Optional[redis.Redis]) -> None:
        """Delete the entire conversation history from Redis."""
        if client is None:
            logger.debug("Redis unavailable — skipping clear_memory")
            return

        try:
            client.delete(MEMORY_KEY)
            logger.info("Conversation memory cleared")
        except redis.RedisError as exc:
            logger.error("Failed to clear memory: %s", exc)

    @_ensure_connection
    def get_memory_count(self, client: Optional[redis.Redis]) -> int:
        """Return the number of entries currently stored in memory."""
        if client is None:
            return 0

        try:
            return client.llen(MEMORY_KEY)
        except redis.RedisError:
            logger.exception("Failed to get memory count")
            return 0

    def format_memory_for_prompt(self, limit: int = 10) -> str:
        """Return memory formatted for a system prompt with long-term and medium-term sections.

        - **Long-term memory**: compressed summary of old exchanges (if summarisation has
          been triggered). Represents conversation history beyond the *limit*.
        - **Medium-term memory**: the *limit* most recent individual exchanges.

        Args:
            limit: Maximum number of medium-term entries to include (default 10).

        Returns:
            Formatted string with labelled sections, or empty string when there is
            no stored memory at all.
        """
        # Retrieve extra entries so we can locate the summary entry even when
        # it sits alongside recent entries in the list.
        entries = self.get_recent_memory(limit=limit + 5)
        if not entries:
            return ""

        long_term_entries: list[str] = []
        medium_term_entries: list[str] = []

        for entry in entries:
            if entry.get("question") == "[SYSTEM SUMMARY]":
                long_term_entries.append(entry.get("answer", ""))
            else:
                medium_term_entries.append(entry)

        medium_term_entries = medium_term_entries[:limit]

        parts: list[str] = []

        if long_term_entries:
            summary_text = "\n".join(long_term_entries)
            parts.append(
                "**Long-term Memory (compressed from earlier conversations):**\n"
                + summary_text
            )

        if medium_term_entries:
            lines = ["**Medium-term Memory (recent exchanges, most recent first):**"]
            for entry in medium_term_entries:
                lines.append(f"User: {entry.get('question', '')}")
                lines.append(f"Assistant: {entry.get('answer', '')}")
                lines.append("---")
            parts.append("\n".join(lines))

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Memory summarisation
    # ------------------------------------------------------------------

    @_ensure_connection
    def _summarize_memory(self, client: Optional[redis.Redis]) -> None:  # noqa: C901
        """Compress old entries into a single summary entry.

        Triggered automatically when the list exceeds ``MAX_MESSAGES_BEFORE_SUMMARY``.

        Strategy:
          1. Keep the ``KEEP_ON_SUMMARY`` most recent entries intact.
          2. Merge all older entries into one summary entry using keyword extraction.
          3. Replace the list with [summary_entry, *recent_entries].
        """
        if client is None:
            return

        try:
            all_entries = client.lrange(MEMORY_KEY, 0, -1)
        except redis.RedisError as exc:
            logger.error("Failed to read memory for summarisation: %s", exc)
            return

        if not all_entries or len(all_entries) <= KEEP_ON_SUMMARY:
            return

        # all_entries[0] is newest (LPUSH), so older entries are toward the end
        # Keep only the KEEP_ON_SUMMARY newest entries as medium-term;
        # everything older is compressed into the long-term summary.
        to_summarize = all_entries[KEEP_ON_SUMMARY:]
        to_keep = all_entries[:KEEP_ON_SUMMARY]

        parsed = []
        for raw in to_summarize:
            try:
                parsed.append(json.loads(raw))
            except (json.JSONDecodeError, TypeError):
                continue

        summary_text = self._build_summary(parsed)

        summary_entry = json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "question": "[SYSTEM SUMMARY]",
                "answer": summary_text,
            },
            ensure_ascii=False,
        )

        # Rebuild the list as: [long-term summary, *medium-term entries]
        # Medium-term entries are stored newest-first (matching LPUSH order).
        try:
            pipe = client.pipeline()
            pipe.delete(MEMORY_KEY)
            pipe.rpush(MEMORY_KEY, summary_entry)
            for entry in reversed(to_keep):
                pipe.rpush(MEMORY_KEY, entry)
            pipe.expire(MEMORY_KEY, TTL_SECONDS)
            pipe.execute()
            logger.info("Memory summarised — %d older entries compressed", len(to_summarize))
        except redis.RedisError as exc:
            logger.error("Failed to write summarised memory: %s", exc)

    @staticmethod
    def _build_summary(entries: list[dict]) -> str:
        """Create a concise summary of the given conversation entries.

        Uses simple keyword extraction.  In production this could be replaced
        with an LLM call for richer summarisation.
        """
        topics: set[str] = set()
        key_exchanges: list[str] = []

        for entry in entries:
            q = entry.get("question", "")
            a = entry.get("answer", "")
            words = (q + " " + a).lower().split()
            topics.update(w for w in words if len(w) > 4)

            # Capture key question-answer pairs that stand out
            if len(q) > 20 and len(a) > 50:
                key_exchanges.append(f"User asked about \"{q[:60]}\"")

        topic_list = sorted(topics)[:30]
        exchange_list = key_exchanges[:5]

        parts: list[str] = []
        if exchange_list:
            parts.append("Key exchanges: " + "; ".join(exchange_list) + ".")
        if topic_list:
            parts.append("Covered topics: " + ", ".join(topic_list) + ".")
        parts.append(f"[Summary of {len(entries)} prior exchanges]")

        return " ".join(parts)
