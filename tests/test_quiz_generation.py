"""Tests for quiz generation: chapter selection and duplicate removal."""

from __future__ import annotations

import pytest

from quiz import quiz_service as qs
from quiz.quiz_service import QuizService


def test_select_chapters_never_repeats_when_enough_distinct_chapters() -> None:
    completed = [(1, 1), (1, 2), (1, 3), (1, 4), (1, 5), (1, 6)]

    picks = QuizService._select_chapters(completed, {(1, 1)}, 5)

    assert len(picks) == 5
    assert len(set(picks)) == 5


def test_select_chapters_fills_short_material_from_existing_chapters() -> None:
    completed = [(1, 1), (1, 2)]

    picks = QuizService._select_chapters(completed, set(), 10)

    assert len(picks) == 10
    assert set(picks) == {(1, 1), (1, 2)}


def test_normalise_question_ignores_case_punctuation_and_spacing() -> None:
    a = qs._normalise_question("What is an IPO?")
    b = qs._normalise_question("  what   is an ipo ")

    assert a == b


def test_generate_quiz_returns_fewer_when_material_is_short(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = QuizService()
    monkeypatch.setattr(service, "_get_completed_chapters", lambda: [(1, 1)])
    monkeypatch.setattr(service, "_get_user_question_chapters", lambda _c: set())
    monkeypatch.setattr(service, "_fetch_chapter_content", lambda _m, _c: "content")
    monkeypatch.setattr(qs, "resolve_selection", lambda _sid: None)

    def fake_batch(
        module_no: int,
        chapter_no: int,
        batch_size: int,
        content: str,
        selection: object = None,
        existing: list[str] | None = None,
    ) -> list[dict]:
        # Always returns the same two questions, simulating an LLM that repeats itself.
        return [
            {"question": "What is a bond?", "options": {"A": "x"}},
            {"question": "What is equity?", "options": {"A": "x"}},
        ]

    monkeypatch.setattr(service, "_generate_batch", fake_batch)

    stored: dict[str, str] = {}

    class FakeRedis:
        def setex(self, key: str, ttl: int, value: str) -> None:
            stored[key] = value

    monkeypatch.setattr(QuizService, "_redis", staticmethod(lambda: FakeRedis()))

    quiz = service._generate_quiz_sync(10)

    assert quiz["total_questions"] == 2
    questions = quiz["questions"]
    assert isinstance(questions, list)
    texts = [q["question"] for q in questions]
    assert texts == ["What is a bond?", "What is equity?"]


def test_generate_batch_prompt_includes_existing_questions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    class FakeResponse:
        text = "[]"

    class FakeLLM:
        def invoke(self, messages: list[object]) -> FakeResponse:
            captured["prompt"] = str(getattr(messages[1], "content", ""))
            return FakeResponse()

    service = QuizService()
    monkeypatch.setattr(service, "_get_llm", lambda _sel=None: FakeLLM())

    service._generate_batch(1, 1, 2, "material", None, existing=["What is a bond?"])

    assert "What is a bond?" in captured["prompt"]
    assert "Do NOT repeat" in captured["prompt"]
