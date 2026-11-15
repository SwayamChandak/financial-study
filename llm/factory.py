"""One construction path for environment defaults and browser selections."""

from __future__ import annotations

from typing import Literal, TypedDict

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_openai import AzureChatOpenAI
from langsmith import tracing_context  # pyright: ignore[reportUnknownVariableType]

from config.settings import settings
from llm.providers import LLMSelection


class TokenOptions(TypedDict, total=False):
    max_tokens: int


def get_chat_model(
    selection: LLMSelection | None = None,
    *,
    role: Literal["chat", "study"] = "chat",
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> BaseChatModel:
    kwargs: TokenOptions = {}
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    if selection is None:
        name = (
            settings.llm_study_model_name
            if role == "study"
            else settings.llm_chat_model_name
        )
        return init_chat_model(name, temperature=temperature, **kwargs)

    # Browser-supplied credentials must not be captured during construction.
    with tracing_context(enabled=False):
        if selection.provider == "azure_openai":
            return AzureChatOpenAI(
                azure_endpoint=selection.endpoint,
                azure_deployment=selection.deployment,
                api_version=selection.api_version,
                api_key=selection.api_key,
                temperature=temperature,
                max_completion_tokens=max_tokens,
                timeout=30,
                max_retries=0,
            )
        if selection.provider == "ollama":
            return init_chat_model(
                f"ollama:{selection.model}",
                temperature=temperature,
                base_url=selection.base_url or settings.ollama_base_url,
                client_kwargs={"timeout": 30},
                **kwargs,
            )
        name = (
            selection.model
            if selection.provider == "custom"
            else f"{selection.provider}:{selection.model}"
        )
        return init_chat_model(
            name,
            temperature=temperature,
            api_key=selection.api_key.get_secret_value() if selection.api_key else None,
            timeout=30,
            max_retries=0,
            **kwargs,
        )
