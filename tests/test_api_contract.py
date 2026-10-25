"""Contract tests for the public FastAPI endpoints."""

from __future__ import annotations

import sys
from types import ModuleType

import pytest
from fastapi.testclient import TestClient

from frontend import server
from memory import memory_service

client = TestClient(server.app)


def empty_memory_prompt(limit: int) -> str:
    return ""


def ignore_memory(question: str, answer: str) -> None:
    return None


def ignore_progress(value: int) -> None:
    return None


def get_current_module() -> int:
    return 2


def get_current_chapter() -> int:
    return 3


def study_result() -> dict[str, str]:
    return {"summary": "Chapter summary"}


def next_study_result() -> dict[str, str]:
    return {"summary": "Next chapter"}


class FakeGraph:
    """Return a deterministic result for chat graph invocations."""

    def invoke(self, state: dict[str, str]) -> dict[str, str]:
        return {"chatbot_response": f"reply: {state['user_input']}"}


def test_chat_request_and_response_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    graph_module = ModuleType("graph.graph_builder")
    graph_module.build_chat_graph = FakeGraph  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "graph.graph_builder", graph_module)
    monkeypatch.setattr(memory_service, "format_memory_for_prompt", empty_memory_prompt)
    monkeypatch.setattr(memory_service, "add_to_memory", ignore_memory)

    response = client.post("/api/chat", json={"query": "What is a bond?"})

    assert response.status_code == 200
    assert response.json() == {"response": "reply: What is a bond?"}


def test_quiz_generation_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    async def generate_quiz(*, count: int) -> dict[str, object]:
        assert count == 2
        return {
            "quiz_id": "quiz-1",
            "created_at": "2026-01-01T00:00:00+00:00",
            "total_questions": 1,
            "questions": [{"id": 1, "question": "Q?", "options": {"A": "A"}}],
        }

    monkeypatch.setattr("quiz.quiz_service.quiz_service.generate_quiz", generate_quiz)

    response = client.post("/api/quiz/generate", json={"count": 2})

    assert response.status_code == 200
    assert response.json()["quiz_id"] == "quiz-1"
    assert response.json()["total_questions"] == 1
    assert "correct_answer" not in response.json()["questions"][0]


def test_quiz_submission_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    async def submit_quiz(quiz_id: str, answers: dict[str, str]) -> dict[str, object]:
        assert quiz_id == "quiz-1"
        assert answers == {"1": "A"}
        return {
            "quiz_id": quiz_id,
            "score": "1/1",
            "percentage": 100,
            "results": [],
        }

    monkeypatch.setattr("quiz.quiz_service.quiz_service.submit_quiz", submit_quiz)

    response = client.post(
        "/api/quiz/submit",
        json={"quiz_id": "quiz-1", "answers": {"1": "A"}},
    )

    assert response.status_code == 200
    assert response.json() == {
        "quiz_id": "quiz-1",
        "score": "1/1",
        "percentage": 100,
        "results": [],
    }


def test_teach_start_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("memory.progress.set_current_module", ignore_progress)
    monkeypatch.setattr("memory.progress.set_current_chapter", ignore_progress)
    monkeypatch.setattr(server, "_run_study_graph", study_result)

    response = client.post("/api/teach/start")

    assert response.status_code == 200
    assert response.json() == {
        "summary": "Chapter summary",
        "module": 1,
        "chapter": 1,
        "done": False,
    }


def test_teach_next_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("memory.progress.get_current_module", get_current_module)
    monkeypatch.setattr("memory.progress.get_current_chapter", get_current_chapter)
    monkeypatch.setattr(server, "_run_study_graph", next_study_result)

    response = client.post("/api/teach/next")

    assert response.status_code == 200
    assert response.json() == {
        "summary": "Next chapter",
        "module": 2,
        "chapter": 3,
        "done": False,
    }
