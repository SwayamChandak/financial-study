"""Unit tests for grading quiz submissions."""

from __future__ import annotations

from typing import TypedDict, cast

import pytest

from quiz.quiz_service import QuizService


class GradedAnswer(TypedDict):
    question_id: str
    question: str
    options: dict[str, str]
    user_answer: str
    correct_answer: str
    is_correct: bool
    explanation: str
    source: str


class GradingResult(TypedDict):
    quiz_id: str
    score: str
    percentage: int
    results: list[GradedAnswer]


@pytest.mark.asyncio
async def test_submit_quiz_grades_answers_without_external_services(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    full_quiz: dict[str, object] = {
        "quiz_id": "quiz-1",
        "questions": [
            {
                "id": 1,
                "question": "What is a bond?",
                "options": {"A": "Debt", "B": "Equity"},
                "correct_answer": "A",
                "explanation": "A bond is debt.",
                "source": "Module 1, Chapter 1",
            },
            {
                "id": 2,
                "question": "What is a share?",
                "options": {"A": "Debt", "B": "Ownership"},
                "correct_answer": "B",
                "explanation": "A share represents ownership.",
                "source": "Module 1, Chapter 2",
            },
        ],
    }
    service = QuizService()

    def get_quiz(quiz_id: str) -> dict[str, object]:
        assert quiz_id == "quiz-1"
        return full_quiz

    monkeypatch.setattr(service, "get_quiz", get_quiz)

    result = cast(GradingResult, await service.submit_quiz("quiz-1", {"1": " a "}))

    assert result["quiz_id"] == "quiz-1"
    assert result["score"] == "1/2"
    assert result["percentage"] == 50
    assert result["results"][0]["is_correct"] is True
    assert result["results"][1]["is_correct"] is False
    assert result["results"][1]["correct_answer"] == "B"
