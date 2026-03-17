"""Provider-agnostic LLM client wrapper."""

from __future__ import annotations

import os
from typing import Any

from use_anything.analyze.providers import (
    AnthropicProvider,
    CodexCLIProvider,
    JSONProvider,
    OpenAIProvider,
)
from use_anything.exceptions import AnalyzeError

DEFAULT_CLAUDE_MODEL = "claude-sonnet-4-6"
DEFAULT_OPENAI_MODEL = "gpt-4.1"
CODEX_CLI_MODEL = "codex-cli"


class LLMClient:
    """Dispatch analysis prompts to Anthropic or OpenAI provider adapters."""

    def __init__(
        self,
        *,
        model: str | None = None,
        anthropic_api_key: str | None = None,
        openai_api_key: str | None = None,
        timeout_seconds: int = 60,
        max_retries: int = 2,
    ) -> None:
        self.model = model
        self.anthropic_api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._provider = self._build_provider()

    def _build_provider(self) -> JSONProvider:
        model = (self.model or "").lower()

        if model == CODEX_CLI_MODEL:
            return CodexCLIProvider(
                timeout_seconds=self.timeout_seconds,
                max_retries=self.max_retries,
            )

        if model.startswith("gpt") or model.startswith("o") or "openai" in model:
            if not self.openai_api_key:
                raise AnalyzeError("OPENAI_API_KEY is required when using OpenAI models")
            return OpenAIProvider(
                api_key=self.openai_api_key,
                model=self.model or DEFAULT_OPENAI_MODEL,
                timeout_seconds=self.timeout_seconds,
                max_retries=self.max_retries,
            )

        if model.startswith("claude") or "anthropic" in model or not model:
            if self.anthropic_api_key:
                return AnthropicProvider(
                    api_key=self.anthropic_api_key,
                    model=self.model or DEFAULT_CLAUDE_MODEL,
                    timeout_seconds=self.timeout_seconds,
                    max_retries=self.max_retries,
                )
            if self.openai_api_key:
                return OpenAIProvider(
                    api_key=self.openai_api_key,
                    model=self.model or DEFAULT_OPENAI_MODEL,
                    timeout_seconds=self.timeout_seconds,
                    max_retries=self.max_retries,
                )

        raise AnalyzeError(
            "No API key configured. Set ANTHROPIC_API_KEY or OPENAI_API_KEY, "
            "or run with --model codex-cli."
        )

    def analyze(self, *, system_prompt: str, user_prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        return self._provider.complete_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=schema,
        )
