"""Provider adapters for Anthropic and OpenAI JSON generation."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any, Protocol

from use_anything.exceptions import AnalyzeError


class JSONProvider(Protocol):
    def complete_json(self, *, system_prompt: str, user_prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Return a JSON object for the prompt."""


@dataclass
class AnthropicProvider:
    api_key: str
    model: str
    timeout_seconds: int = 60
    max_retries: int = 2

    def complete_json(self, *, system_prompt: str, user_prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        try:
            import anthropic
        except ImportError as exc:
            raise AnalyzeError("anthropic package is required for Anthropic models") from exc

        client = anthropic.Anthropic(api_key=self.api_key, timeout=self.timeout_seconds)
        prompt = f"{user_prompt}\n\nJSON schema:\n{json.dumps(schema, indent=2)}"

        def _request() -> str:
            response = client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=0,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}],
            )
            return "\n".join(
                block.text for block in response.content if getattr(block, "type", "") == "text"
            )

        text = _with_retry(_request, retries=self.max_retries)
        return _extract_json(text)


@dataclass
class OpenAIProvider:
    api_key: str
    model: str
    timeout_seconds: int = 60
    max_retries: int = 2

    def complete_json(self, *, system_prompt: str, user_prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise AnalyzeError("openai package is required for OpenAI models") from exc

        client = OpenAI(api_key=self.api_key, timeout=self.timeout_seconds)

        def _request() -> str:
            response = client.chat.completions.create(
                model=self.model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": f"{user_prompt}\n\nJSON schema:\n{json.dumps(schema, indent=2)}",
                    },
                ],
            )
            content = response.choices[0].message.content
            return content or "{}"

        text = _with_retry(_request, retries=self.max_retries)
        return _extract_json(text)


def _with_retry(fn, retries: int) -> str:
    attempt = 0
    last_error: Exception | None = None
    while attempt <= retries:
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            attempt += 1
            if attempt > retries:
                break
            time.sleep(min(2**attempt, 4))
    raise AnalyzeError(f"LLM request failed after {retries + 1} attempts: {last_error}") from last_error


def _extract_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        raise AnalyzeError("LLM returned empty response")

    try:
        payload = json.loads(stripped)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", stripped, re.DOTALL)
    if not match:
        raise AnalyzeError("LLM response did not contain a JSON object")

    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise AnalyzeError(f"LLM returned invalid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise AnalyzeError("LLM JSON response must be an object")
    return payload
