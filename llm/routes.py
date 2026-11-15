"""Browser settings endpoints; only encrypted Redis stores secret values."""

from __future__ import annotations

import logging
from time import perf_counter
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from langsmith import tracing_context  # pyright: ignore[reportUnknownVariableType]
from pydantic import ValidationError

from config.settings import settings
from llm.credentials import credential_store, resolve_selection, valid_session_id
from llm.factory import get_chat_model
from llm.providers import (
    PROVIDERS,
    LLMConfigInput,
    ProviderSpec,
    public_config,
    selection_from_input,
)

logger = logging.getLogger(__name__)
COOKIE_NAME = "llm_sid"
router = APIRouter(prefix="/api/llm", tags=["LLM settings"])


def session_id(request: Request) -> str | None:
    return valid_session_id(request.cookies.get(COOKIE_NAME))


def check_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    expected = urlsplit(str(request.base_url))
    if request.headers.get("sec-fetch-site") == "cross-site" or (
        origin and urlsplit(origin)[:2] != expected[:2]
    ):
        raise HTTPException(403, "Cross-origin settings requests are not allowed.")


def set_session_cookie(request: Request, response: Response, value: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        value,
        max_age=settings.llm_session_ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
    )
    response.headers["Cache-Control"] = "no-store"


async def safe_validation_error(
    request: Request,
    exc: Exception,
) -> Response:
    if not isinstance(exc, RequestValidationError):
        raise exc
    if request.url.path.startswith("/api/llm/"):
        # FastAPI's default validation response includes the submitted input.
        return JSONResponse(
            status_code=422,
            content={"error": "Invalid LLM configuration."},
            headers={"Cache-Control": "no-store"},
        )
    return await request_validation_exception_handler(request, exc)


@router.get("/providers")
def providers() -> list[ProviderSpec]:
    return PROVIDERS


@router.get("/config")
def get_config(request: Request, response: Response) -> dict[str, object]:
    existing_id = session_id(request)
    selection = resolve_selection(existing_id)
    set_session_cookie(request, response, existing_id or str(uuid4()))
    return {
        **public_config(selection),
        "defaults": {
            "chat": settings.llm_chat_model_name,
            "study": settings.llm_study_model_name,
            "ollama_base_url": settings.ollama_base_url,
        },
        "ttl_seconds": settings.llm_session_ttl_seconds,
    }


@router.put("/config")
def save_config(
    config: LLMConfigInput,
    request: Request,
    response: Response,
) -> dict[str, object]:
    check_origin(request)
    old_id = session_id(request)
    previous = resolve_selection(old_id) if config.api_key is None else None
    try:
        selection = selection_from_input(config, previous)
    except ValidationError:
        raise HTTPException(
            422, "A valid API key and provider fields are required."
        ) from None
    new_id = str(uuid4())
    credential_store.save(new_id, selection)
    if old_id:
        credential_store.delete(old_id)
    set_session_cookie(request, response, new_id)
    return public_config(selection)


@router.delete("/config")
def clear_config(request: Request, response: Response) -> dict[str, object]:
    check_origin(request)
    existing_id = session_id(request)
    if existing_id:
        credential_store.delete(existing_id)
    response.delete_cookie(
        COOKIE_NAME,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
    )
    response.headers["Cache-Control"] = "no-store"
    return public_config(None)


@router.post("/test")
def test_connection(
    request: Request,
    config: LLMConfigInput | None = None,
) -> JSONResponse:
    check_origin(request)
    previous = resolve_selection(session_id(request))
    try:
        selection = selection_from_input(config, previous) if config else previous
    except ValidationError:
        raise HTTPException(
            422, "A valid API key and provider fields are required."
        ) from None
    started = perf_counter()
    try:
        with tracing_context(enabled=False):
            model = get_chat_model(selection, max_tokens=8)
            model.invoke("Reply with OK.")
    except Exception:
        # Provider messages can contain credentials, URLs, or echoed headers.
        logger.warning("LLM connection test failed; provider details suppressed.")
        return JSONResponse(
            status_code=502,
            content={
                "ok": False,
                "error": (
                    "Provider connection failed. Check the key, model, endpoint, "
                    "installed provider package, and provider access."
                ),
            },
            headers={"Cache-Control": "no-store"},
        )
    return JSONResponse(
        content={"ok": True, "latency_ms": round((perf_counter() - started) * 1000)},
        headers={"Cache-Control": "no-store"},
    )
