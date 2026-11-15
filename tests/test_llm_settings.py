"""Offline tests for provider construction, credential isolation and HTTP contracts."""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langsmith import (
    get_tracing_context,  # pyright: ignore[reportUnknownVariableType]
    tracing_context,  # pyright: ignore[reportUnknownVariableType]
)
from pydantic import SecretStr, ValidationError

from config.settings import settings
from frontend import server
from graph import chat_nodes, study_nodes
from graph.graph_builder import build_study_graph
from llm import factory
from llm.credentials import CredentialStoreError, credential_store, resolve_selection
from llm.providers import LLMConfigInput, LLMSelection, selection_from_input
from quiz.quiz_service import QuizService

TEST_KEY = "test-only-provider-secret-12345678"


@pytest.fixture(autouse=True)
def disable_test_tracing() -> Iterator[None]:
    with tracing_context(enabled=False):
        yield


def ignore(*args: object, **kwargs: object) -> None:
    return None


def empty_memory(*, limit: int) -> str:
    return ""


def seen_chunks(query: str, top_k: int) -> list[Document]:
    return [Document(page_content="A bond is debt.")]


def ok_model(*args: object, **kwargs: object) -> BaseChatModel:
    return FakeListChatModel(responses=["OK"])


def no_question_chapters(
    completed: list[tuple[int, int]],
) -> set[tuple[int, int]]:
    return set()


def chapter_content(module_no: int, chapter_no: int) -> str:
    return "A bond is debt."


def chapter_chunks(
    module_no: int,
    chapter_no: int,
) -> tuple[list[Document], list[str]]:
    return (
        ([Document(page_content="x" * 100)], ["point"]) if chapter_no == 1 else ([], [])
    )


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, tuple[bytes, float]] = {}

    def setex(self, name: str, ttl: int, value: bytes) -> None:
        self.values[name] = (value, time.monotonic() + ttl)

    def get(self, name: str) -> bytes | None:
        entry = self.values.get(name)
        if entry is None or entry[1] <= time.monotonic():
            return None
        return entry[0]

    def delete(self, name: str) -> None:
        self.values.pop(name, None)


@pytest.fixture
def encrypted_store(monkeypatch: pytest.MonkeyPatch) -> FakeRedis:
    backend = FakeRedis()
    monkeypatch.setattr(credential_store, "_redis", backend)
    monkeypatch.setattr(
        settings,
        "llm_key_encryption_key",
        SecretStr(Fernet.generate_key().decode()),
    )
    return backend


@pytest.fixture
def client(encrypted_store: FakeRedis) -> Iterator[TestClient]:
    with TestClient(server.app) as http:
        yield http


def selection(model: str = "claude-sonnet-4-5") -> LLMSelection:
    return LLMSelection(
        provider="anthropic",
        model=model,
        api_key=SecretStr(TEST_KEY),
    )


def test_credentials_are_encrypted_expiring_and_clearable(
    encrypted_store: FakeRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sid = str(uuid4())
    credential_store.save(sid, selection())
    key = f"llm:sess:{sid}"
    ciphertext, expires = encrypted_store.values[key]
    assert TEST_KEY.encode() not in ciphertext
    assert b"anthropic" not in ciphertext
    assert expires - time.monotonic() <= settings.llm_session_ttl_seconds
    assert resolve_selection(sid) == selection()
    encrypted_store.values[key] = (ciphertext, time.monotonic() - 1)
    assert resolve_selection(sid) is None
    credential_store.save(sid, selection())
    monkeypatch.setattr(
        settings,
        "llm_key_encryption_key",
        SecretStr(Fernet.generate_key().decode()),
    )
    with pytest.raises(CredentialStoreError):
        resolve_selection(sid)
    credential_store.delete(sid)
    assert resolve_selection(sid) is None


def test_missing_encryption_key_never_saves_plaintext(
    encrypted_store: FakeRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "llm_key_encryption_key", SecretStr(""))
    with pytest.raises(CredentialStoreError):
        credential_store.save(str(uuid4()), selection())
    assert not encrypted_store.values


def test_provider_models_construct_offline() -> None:
    cases = [
        (LLMSelection(provider="ollama", model="llama3.2"), "ChatOllama"),
        (selection(), "ChatAnthropic"),
        (
            LLMSelection(
                provider="google_genai",
                model="gemini-2.5-flash",
                api_key=SecretStr(TEST_KEY),
            ),
            "ChatGoogleGenerativeAI",
        ),
        (
            LLMSelection(
                provider="azure_openai",
                endpoint="https://example.openai.azure.com",
                api_version="2024-10-21",
                deployment="test-deployment",
                api_key=SecretStr(TEST_KEY),
            ),
            "AzureChatOpenAI",
        ),
        (
            LLMSelection(
                provider="custom",
                model="openai:gpt-4o-mini",
                api_key=SecretStr(TEST_KEY),
            ),
            "ChatOpenAI",
        ),
    ]
    for config, expected in cases:
        model = factory.get_chat_model(config, max_tokens=8)
        assert type(model).__name__ == expected


def test_environment_defaults_remain_role_specific(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[str, float]] = []

    def init_model(name: str, *, temperature: float) -> BaseChatModel:
        seen.append((name, temperature))
        return FakeListChatModel(responses=["OK"])

    monkeypatch.setattr(factory, "init_chat_model", init_model)
    monkeypatch.setattr(settings, "llm_chat_model_name", "ollama:chat-default")
    monkeypatch.setattr(settings, "llm_study_model_name", "ollama:study-default")
    factory.get_chat_model()
    factory.get_chat_model(role="study", temperature=0.2)
    assert seen == [("ollama:chat-default", 0.0), ("ollama:study-default", 0.2)]


@pytest.mark.parametrize(
    "config",
    [
        {"provider": "anthropic", "model": "claude-sonnet-4-5"},
        {"provider": "azure_openai", "api_key": TEST_KEY},
        {"provider": "custom", "model": "missing-provider"},
        {"provider": "ollama", "model": ""},
        {"provider": "ollama", "model": "llama3.2", "base_url": "file:///etc/passwd"},
        {
            "provider": "ollama",
            "model": "llama3.2",
            "base_url": "http://user:pass@host",
        },
        {"provider": "ollama", "model": "llama3.2", "api_key": TEST_KEY},
    ],
)
def test_invalid_selections(config: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        LLMSelection.model_validate(config)


def test_key_is_not_reused_for_another_custom_provider() -> None:
    previous = LLMSelection(
        provider="custom",
        model="openai:model",
        api_key=SecretStr(TEST_KEY),
    )
    new = selection_from_input(
        LLMConfigInput(provider="custom", model="anthropic:model"),
        previous,
    )
    assert new.api_key is None


def test_http_config_contract_never_returns_the_key(client: TestClient) -> None:
    metadata = client.get("/api/llm/providers")
    assert {p["id"] for p in metadata.json()} == {
        "ollama",
        "anthropic",
        "azure_openai",
        "google_genai",
        "custom",
    }
    initial = client.get("/api/llm/config")
    assert initial.json()["selection"] is None
    assert "httponly" in initial.headers["set-cookie"].lower()
    assert "samesite=lax" in initial.headers["set-cookie"].lower()
    saved = client.put(
        "/api/llm/config",
        json={
            "provider": "anthropic",
            "model": "claude-sonnet-4-5",
            "api_key": TEST_KEY,
        },
    )
    assert saved.status_code == 200
    assert saved.json()["has_key"] is True
    assert saved.json()["masked_key"] == "********5678"
    assert TEST_KEY not in saved.text
    assert "api_key" not in saved.json()["selection"]
    read = client.get("/api/llm/config")
    assert TEST_KEY not in read.text
    assert read.headers["cache-control"] == "no-store"
    changed = client.put(
        "/api/llm/config",
        json={
            "provider": "anthropic",
            "model": "another-model",
        },
    )
    assert changed.status_code == 200
    assert changed.json()["has_key"] is True
    assert client.delete("/api/llm/config").json()["selection"] is None
    assert client.get("/api/llm/config").json()["selection"] is None


def test_validation_and_provider_errors_do_not_echo_keys(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    bad = client.put(
        "/api/llm/config",
        json={
            "provider": "azure_openai",
            "api_key": TEST_KEY,
            "endpoint": "not-a-url",
        },
    )
    assert bad.status_code == 422
    assert TEST_KEY not in bad.text

    def fail_model(*args: object, **kwargs: object) -> BaseChatModel:
        assert get_tracing_context()["enabled"] is False
        raise ValueError(f"Provider returned authorization {TEST_KEY}")

    monkeypatch.setattr("llm.routes.get_chat_model", fail_model)
    result = client.post(
        "/api/llm/test",
        json={
            "provider": "anthropic",
            "model": "test",
            "api_key": TEST_KEY,
        },
    )
    assert result.status_code == 502
    assert result.json()["ok"] is False
    assert TEST_KEY not in result.text
    assert TEST_KEY not in caplog.text
    assert client.get("/api/llm/config").json()["selection"] is None


def test_test_connection_does_not_save_or_change_selection(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "llm.routes.get_chat_model",
        ok_model,
    )
    result = client.post(
        "/api/llm/test",
        json={
            "provider": "ollama",
            "model": "llama3.2",
        },
    )
    assert result.json()["ok"] is True
    assert isinstance(result.json()["latency_ms"], int)
    assert client.get("/api/llm/config").json()["selection"] is None


def test_cross_origin_mutations_are_rejected(client: TestClient) -> None:
    response = client.put(
        "/api/llm/config",
        headers={"Origin": "https://other.example"},
        json={"provider": "ollama", "model": "llama3.2"},
    )
    assert response.status_code == 403
    assert (
        client.post(
            "/api/llm/test",
            headers={"Sec-Fetch-Site": "cross-site"},
        ).status_code
        == 403
    )


def test_storage_outage_is_explicit(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_save(*args: object) -> None:
        raise CredentialStoreError("Unable to save LLM settings in Redis.")

    monkeypatch.setattr(credential_store, "save", fail_save)
    response = client.put(
        "/api/llm/config",
        json={
            "provider": "ollama",
            "model": "llama3.2",
        },
    )
    assert response.status_code == 503


def test_two_chat_sessions_use_their_own_models(
    encrypted_store: FakeRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []
    instances: list[BaseChatModel] = []

    def build_model(config: LLMSelection | None, **kwargs: object) -> BaseChatModel:
        assert config is not None
        assert get_tracing_context()["enabled"] is False
        seen.append(config.model)
        model = FakeListChatModel(
            responses=["PASS"]
            if len(seen) % 2 == 0
            else ["YES", "YES", "A bond is debt."],
        )
        instances.append(model)
        return model

    monkeypatch.setattr(chat_nodes, "get_chat_model", build_model)
    monkeypatch.setattr(
        chat_nodes,
        "search_seen_chunks",
        seen_chunks,
    )
    monkeypatch.setattr("memory.memory_service.format_memory_for_prompt", empty_memory)
    monkeypatch.setattr("memory.memory_service.add_to_memory", ignore)
    with TestClient(server.app) as first, TestClient(server.app) as second:
        for http, model in [(first, "model-one"), (second, "model-two")]:
            assert (
                http.put(
                    "/api/llm/config",
                    json={
                        "provider": "anthropic",
                        "model": model,
                        "api_key": TEST_KEY,
                    },
                ).status_code
                == 200
            )
            response = http.post("/api/chat", json={"query": "What is a bond?"})
            assert response.status_code == 200
            assert TEST_KEY not in response.text
    assert seen == ["model-one", "model-one", "model-two", "model-two"]
    assert instances[0] is not instances[2]


@pytest.mark.asyncio
async def test_quiz_worker_uses_request_selection_without_singleton(
    encrypted_store: FakeRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []
    service = QuizService()

    def model_for_selection(
        config: LLMSelection | None,
        **kwargs: object,
    ) -> BaseChatModel:
        assert config is not None
        seen.append(config.model)
        return FakeListChatModel(
            responses=[
                json.dumps(
                    [
                        {
                            "question": "Bond?",
                            "options": {"A": "Debt"},
                            "correct_answer": "A",
                            "explanation": "Debt",
                            "source": "Chapter 1",
                        }
                    ]
                )
            ]
        )

    monkeypatch.setattr("quiz.quiz_service.get_chat_model", model_for_selection)
    monkeypatch.setattr(service, "_get_completed_chapters", lambda: [(1, 1)])
    monkeypatch.setattr(service, "_get_user_question_chapters", no_question_chapters)
    monkeypatch.setattr(service, "_fetch_chapter_content", chapter_content)
    monkeypatch.setattr(service, "_redis", lambda: encrypted_store)
    for name in ("model-one", "model-two"):
        sid = str(uuid4())
        credential_store.save(sid, selection(name))
        result = await service.generate_quiz(count=1, llm_session_id=sid)
        assert result["total_questions"] == 1
        assert '"correct_answer"' not in json.dumps(result)
    assert seen == ["model-one", "model-two"]


def test_study_graph_uses_selection_for_generation_and_validation(
    encrypted_store: FakeRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sid = str(uuid4())
    credential_store.save(sid, selection("study-selection"))
    seen: list[tuple[str, str]] = []

    def build_model(
        config: LLMSelection | None,
        *,
        role: str,
        **kwargs: object,
    ) -> BaseChatModel:
        assert config is not None
        seen.append((config.model, role))
        return FakeListChatModel(
            responses=["PASS"] if len(seen) % 2 == 0 else ["x" * 60],
        )

    monkeypatch.setattr(study_nodes, "get_chat_model", build_model)
    monkeypatch.setattr(study_nodes, "keys_exist", lambda: (True, True))
    monkeypatch.setattr(study_nodes, "get_current_module", lambda: 1)
    monkeypatch.setattr(study_nodes, "get_current_chapter", lambda: 1)
    monkeypatch.setattr(
        study_nodes,
        "fetch_all_chunks",
        chapter_chunks,
    )
    monkeypatch.setattr(study_nodes, "mark_chunks_seen", ignore)
    monkeypatch.setattr(study_nodes, "set_current_module", ignore)
    monkeypatch.setattr(study_nodes, "set_current_chapter", ignore)
    result = build_study_graph().invoke({"llm_session_id": sid})
    assert result["summary"] == "x" * 60
    assert all(value == ("study-selection", "study") for value in seen)
    assert len(seen) == 2
    assert TEST_KEY not in json.dumps(result, default=str)
