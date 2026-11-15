"""Provider metadata and validated, non-global model selections."""

from __future__ import annotations

import re
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

Provider = Literal["ollama", "anthropic", "azure_openai", "google_genai", "custom"]
_KEY_SUFFIX_LENGTH = 4


class ProviderSpec(BaseModel):
    id: Provider
    label: str
    required_fields: list[str]
    optional_fields: list[str]
    models: list[str]


PROVIDERS = [
    ProviderSpec(
        id="ollama",
        label="Ollama",
        required_fields=["model"],
        optional_fields=["base_url"],
        models=["llama3.2", "qwen3"],
    ),
    ProviderSpec(
        id="anthropic",
        label="Anthropic Claude",
        required_fields=["model", "api_key"],
        optional_fields=[],
        models=["claude-sonnet-4-5", "claude-haiku-4-5"],
    ),
    ProviderSpec(
        id="azure_openai",
        label="Azure OpenAI",
        required_fields=["endpoint", "api_version", "deployment", "api_key"],
        optional_fields=[],
        models=[],
    ),
    ProviderSpec(
        id="google_genai",
        label="Google Gemini",
        required_fields=["model", "api_key"],
        optional_fields=[],
        models=["gemini-2.5-flash", "gemini-2.5-pro"],
    ),
    ProviderSpec(
        id="custom",
        label="Custom LangChain provider:model",
        required_fields=["model"],
        optional_fields=["api_key"],
        models=[],
    ),
]


class LLMConfigInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    provider: Provider
    model: str = Field(default="", max_length=200)
    api_key: SecretStr | None = Field(default=None, max_length=8192)
    base_url: str | None = Field(default=None, max_length=2048)
    endpoint: str | None = Field(default=None, max_length=2048)
    api_version: str | None = Field(default=None, max_length=100)
    deployment: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def validate_provider_fields(self) -> Self:
        if self.provider != "azure_openai" and not self.model:
            raise ValueError("A model is required.")
        if self.provider == "custom" and not re.fullmatch(
            r"[a-z][a-z0-9_]*:[A-Za-z0-9_./:@-]+",
            self.model,
        ):
            raise ValueError("Custom models must use provider:model syntax.")
        if self.provider == "azure_openai" and not all(
            [self.endpoint, self.api_version, self.deployment],
        ):
            raise ValueError("Azure requires endpoint, api_version and deployment.")
        if self.base_url and self.provider != "ollama":
            raise ValueError("base_url is only supported for Ollama.")
        if self.provider == "ollama" and self.api_key:
            raise ValueError("Ollama does not use an API key.")
        if any([self.endpoint, self.api_version, self.deployment]) and (
            self.provider != "azure_openai"
        ):
            raise ValueError("Azure fields are only supported for Azure OpenAI.")
        for value in (self.base_url, self.endpoint):
            if value:
                url = urlsplit(value)
                if (
                    url.scheme not in {"http", "https"}
                    or not url.hostname
                    or url.username
                    or url.password
                    or url.query
                    or url.fragment
                ):
                    raise ValueError("Use an HTTP(S) URL without credentials or query.")
        if self.endpoint and urlsplit(self.endpoint).scheme != "https":
            raise ValueError("Azure endpoints must use HTTPS.")
        return self


class LLMSelection(LLMConfigInput):
    @model_validator(mode="after")
    def require_credentials(self) -> Self:
        if self.provider in {"anthropic", "azure_openai", "google_genai"} and (
            self.api_key is None or not self.api_key.get_secret_value().strip()
        ):
            raise ValueError("An API key is required for this provider.")
        return self


def selection_from_input(
    config: LLMConfigInput,
    previous: LLMSelection | None = None,
) -> LLMSelection:
    data = config.model_dump()
    if (
        config.api_key is None
        and previous
        and previous.provider == config.provider
        and previous.endpoint == config.endpoint
        and (
            config.provider != "custom"
            or previous.model.partition(":")[0] == config.model.partition(":")[0]
        )
    ):
        data["api_key"] = previous.api_key
    return LLMSelection.model_validate(data)


def public_config(selection: LLMSelection | None) -> dict[str, object]:
    if selection is None:
        return {"selection": None, "has_key": False, "masked_key": None}
    key = selection.api_key.get_secret_value() if selection.api_key else ""
    # Never reveal short keys in full, even through the masked view.
    masked = (
        f"********{key[-_KEY_SUFFIX_LENGTH:]}"
        if len(key) > _KEY_SUFFIX_LENGTH
        else "********"
    )
    return {
        "selection": selection.model_dump(exclude={"api_key"}),
        "has_key": bool(key),
        "masked_key": masked if key else None,
    }
