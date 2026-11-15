"""Encrypted Redis selections; credentials never live in graph state."""

from __future__ import annotations

import json
from uuid import UUID

import redis
from cryptography.fernet import Fernet, InvalidToken
from pydantic import ValidationError

from config.settings import settings
from llm.providers import LLMSelection

_SESSION_UUID_VERSION = 4


class CredentialStoreError(Exception):
    """Credential storage is unavailable or cannot decrypt a selection."""


def valid_session_id(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        parsed = UUID(value)
    except ValueError:
        return None
    return str(parsed) if parsed.version == _SESSION_UUID_VERSION else None


class CredentialStore:
    def __init__(self) -> None:
        self._redis: redis.Redis = redis.Redis.from_url(  # pyright: ignore[reportUnknownMemberType]
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
        )

    @staticmethod
    def _cipher() -> Fernet:
        try:
            return Fernet(settings.llm_key_encryption_key.get_secret_value().encode())
        except ValueError:
            raise CredentialStoreError(
                "Configure a valid LLM_KEY_ENCRYPTION_KEY before saving credentials.",
            ) from None

    @staticmethod
    def _key(session_id: str) -> str:
        normalized = valid_session_id(session_id)
        if normalized is None:
            raise CredentialStoreError("Invalid LLM session.")
        return f"llm:sess:{normalized}"

    def get(self, session_id: str) -> LLMSelection | None:
        try:
            raw = self._redis.get(self._key(session_id))
            if raw is None:
                return None
            decrypted = self._cipher().decrypt(
                raw.encode() if isinstance(raw, str) else raw,
            )
            return LLMSelection.model_validate_json(decrypted)
        except (redis.RedisError, InvalidToken, ValidationError):
            raise CredentialStoreError(
                "LLM settings are unavailable. Check Redis and the encryption key.",
            ) from None

    def save(self, session_id: str, selection: LLMSelection) -> None:
        data = selection.model_dump(mode="json", exclude={"api_key"})
        data["api_key"] = (
            selection.api_key.get_secret_value() if selection.api_key else None
        )
        encrypted = self._cipher().encrypt(json.dumps(data).encode())
        try:
            self._redis.setex(
                self._key(session_id),
                settings.llm_session_ttl_seconds,
                encrypted,
            )
        except redis.RedisError:
            raise CredentialStoreError(
                "Unable to save LLM settings in Redis."
            ) from None

    def delete(self, session_id: str) -> None:
        try:
            self._redis.delete(self._key(session_id))
        except redis.RedisError:
            raise CredentialStoreError(
                "Unable to clear LLM settings in Redis."
            ) from None


credential_store = CredentialStore()


def resolve_selection(session_id: str | None) -> LLMSelection | None:
    return credential_store.get(session_id) if session_id else None
