from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

from config.settings import setup_langsmith

setup_langsmith()

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Financial Study Chatbot")


class ChatRequest(BaseModel):
    query: str


class ChatResponse(BaseModel):
    response: str


@app.post("/api/chat")
async def chat(req: ChatRequest) -> ChatResponse:
    from graph.graph_builder import build_chat_graph
    from memory import memory_service

    memory_context = memory_service.format_memory_for_prompt(limit=10)

    graph = build_chat_graph()
    result = graph.invoke({
        "user_input": req.query,
        "memory_context": memory_context,
    })

    response_text = result.get("chatbot_response", "")
    memory_service.add_to_memory(req.query, response_text)
    return ChatResponse(response=response_text)


class QuizGenerateRequest(BaseModel):
    count: int = 10


class QuizGenerateResponse(BaseModel):
    quiz_id: str
    created_at: str
    total_questions: int
    questions: list[dict]


class QuizSubmitRequest(BaseModel):
    quiz_id: str
    answers: dict[str, str]


class QuizSubmitResponse(BaseModel):
    quiz_id: str
    score: str
    percentage: int
    results: list[dict]


@app.post("/api/quiz/generate")
async def quiz_generate(req: QuizGenerateRequest) -> QuizGenerateResponse:
    from quiz.quiz_service import quiz_service

    try:
        result = await quiz_service.generate_quiz(count=req.count)
        return QuizGenerateResponse(**result)
    except Exception as exc:
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=400,
            content={"error": str(exc)},
        )


@app.post("/api/quiz/submit")
async def quiz_submit(req: QuizSubmitRequest) -> QuizSubmitResponse:
    from quiz.quiz_service import quiz_service

    try:
        result = await quiz_service.submit_quiz(req.quiz_id, req.answers)
        return QuizSubmitResponse(**result)
    except Exception as exc:
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=404,
            content={"error": str(exc)},
        )


class TeachResponse(BaseModel):
    summary: str
    module: int
    chapter: int
    done: bool


def _run_study_graph() -> dict:
    """Run the full study graph and return the final state."""
    from graph.graph_builder import build_study_graph

    graph = build_study_graph()
    return graph.invoke({})


@app.post("/api/teach/start")
async def teach_start() -> TeachResponse:
    from memory.progress import set_current_chapter, set_current_module

    set_current_module(1)
    set_current_chapter(1)

    result = _run_study_graph()
    summary = result.get("summary", "")

    return TeachResponse(
        summary=summary,
        module=1,
        chapter=1,
        done=not summary,
    )


@app.post("/api/teach/next")
async def teach_next() -> TeachResponse:
    from memory.progress import get_current_chapter, get_current_module

    module = get_current_module()
    chapter = get_current_chapter()

    result = _run_study_graph()
    summary = result.get("summary", "")

    return TeachResponse(
        summary=summary or "No more chapters available — all study material has been covered.",
        module=module,
        chapter=chapter,
        done=not result.get("summary", ""),
    )


app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


def main() -> None:
    uvicorn.run("frontend.server:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
