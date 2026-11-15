from __future__ import annotations

import sys
import logging
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from langsmith import tracing_context  # pyright: ignore[reportUnknownVariableType]
from pydantic import BaseModel

load_dotenv()

from config.settings import setup_langsmith
from llm.credentials import CredentialStoreError
from llm.routes import router as llm_router, safe_validation_error, session_id

setup_langsmith()

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Financial Study Chatbot")
app.include_router(llm_router)
app.add_exception_handler(RequestValidationError, safe_validation_error)
logger = logging.getLogger(__name__)


@app.exception_handler(CredentialStoreError)
async def credential_error(request: Request, exc: CredentialStoreError) -> JSONResponse:
    logger.warning("LLM credential storage operation failed.")
    return JSONResponse(
        status_code=503, content={"error": str(exc)},
        headers={"Cache-Control": "no-store"},
    )


class ChatRequest(BaseModel):
    query: str


class ChatResponse(BaseModel):
    response: str


@app.post("/api/chat")
def chat(req: ChatRequest, request: Request) -> ChatResponse:
    from graph.graph_builder import build_chat_graph
    from memory import memory_service

    try:
        with tracing_context(enabled=False if session_id(request) else None):
            memory_context = memory_service.format_memory_for_prompt(limit=10)
            graph = build_chat_graph()
            result = graph.invoke({
                "user_input": req.query,
                "memory_context": memory_context,
                "llm_session_id": session_id(request),
            })
            response_text = result.get("chatbot_response", "")
            memory_service.add_to_memory(req.query, response_text)
    except CredentialStoreError:
        raise
    except Exception:
        logger.warning("Chat workflow failed; provider details suppressed.")
        raise HTTPException(502, "Chat failed. Check provider and study material.") from None
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


@app.post("/api/quiz/generate", response_model=QuizGenerateResponse)
async def quiz_generate(
    req: QuizGenerateRequest, request: Request,
) -> QuizGenerateResponse | JSONResponse:
    from quiz.quiz_service import quiz_service

    try:
        with tracing_context(enabled=False if session_id(request) else None):
            result = await quiz_service.generate_quiz(
                count=req.count, llm_session_id=session_id(request),
            )
        return QuizGenerateResponse.model_validate(result)
    except CredentialStoreError:
        raise
    except Exception:
        logger.warning("Quiz workflow failed; provider details suppressed.")
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=400,
            content={"error": "Quiz generation failed. Check provider and study material."},
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


def _run_study_graph(llm_session_id: str | None = None) -> dict:
    """Run the full study graph and return the final state."""
    from graph.graph_builder import build_study_graph

    graph = build_study_graph()
    try:
        with tracing_context(enabled=False if llm_session_id else None):
            return graph.invoke({"llm_session_id": llm_session_id})
    except CredentialStoreError:
        raise
    except Exception:
        logger.warning("Study workflow failed; provider details suppressed.")
        raise HTTPException(502, "Study failed. Check provider and study material.") from None


@app.post("/api/teach/start")
def teach_start(request: Request) -> TeachResponse:
    from memory.progress import set_current_chapter, set_current_module

    set_current_module(1)
    set_current_chapter(1)

    result = _run_study_graph(session_id(request))
    summary = result.get("summary", "")

    return TeachResponse(
        summary=summary,
        module=1,
        chapter=1,
        done=not summary,
    )


@app.post("/api/teach/next")
def teach_next(request: Request) -> TeachResponse:
    from memory.progress import get_current_chapter, get_current_module

    module = get_current_module()
    chapter = get_current_chapter()

    result = _run_study_graph(session_id(request))
    summary = result.get("summary", "")

    return TeachResponse(
        summary=summary or "No more chapters available — all study material has been covered.",
        module=module,
        chapter=chapter,
        done=not result.get("summary", ""),
    )


app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


def main() -> None:
    uvicorn.run("frontend.server:app", host="127.0.0.1", port=8010, reload=True)


if __name__ == "__main__":
    main()
