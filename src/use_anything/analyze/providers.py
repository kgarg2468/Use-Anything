"""Provider adapters for Anthropic and OpenAI JSON generation."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
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


@dataclass
class CodexCLIProvider:
    timeout_seconds: int = 60
    max_retries: int = 2
    sandbox_mode: str = "read-only"
    codex_executable: str = "codex"

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        codex_path = shutil.which(self.codex_executable)
        if not codex_path:
            raise AnalyzeError(
                "codex CLI executable not found on PATH. Install Codex CLI and run `codex login`."
            )

        prompt = _build_codex_prompt(system_prompt=system_prompt, user_prompt=user_prompt, schema=schema)

        def _request() -> str:
            with NamedTemporaryFile(prefix="use-anything-codex-", suffix=".txt", delete=False) as handle:
                output_path = Path(handle.name)

            command = [
                codex_path,
                "exec",
                "--skip-git-repo-check",
                "--sandbox",
                self.sandbox_mode,
                "--output-last-message",
                str(output_path),
                prompt,
            ]

            try:
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=self.timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                output_path.unlink(missing_ok=True)
                raise AnalyzeError(f"codex exec timed out after {self.timeout_seconds} seconds") from exc

            if completed.returncode != 0:
                output_path.unlink(missing_ok=True)
                details = _truncate_output(completed.stderr or completed.stdout or "")
                raise AnalyzeError(
                    "codex exec failed "
                    f"(exit {completed.returncode}). "
                    "Ensure Codex is authenticated with `codex login`. "
                    f"Details: {details}"
                )

            text = output_path.read_text().strip() if output_path.exists() else ""
            output_path.unlink(missing_ok=True)

            if not text:
                raise AnalyzeError(
                    "codex exec produced no final message. "
                    "Ensure Codex completed successfully and returned JSON."
                )
            return text

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


def _build_codex_prompt(*, system_prompt: str, user_prompt: str, schema: dict[str, Any]) -> str:
    return (
        f"{system_prompt}\n\n"
        f"{user_prompt}\n\n"
        "Return only a JSON object (no markdown fences, no prose) "
        "matching this schema exactly:\n"
        f"{json.dumps(schema, indent=2)}"
    )


def _truncate_output(output: str, limit: int = 500) -> str:
    stripped = output.strip()
    if not stripped:
        return "(no stderr/stdout)"
    if len(stripped) <= limit:
        return stripped
    return f"{stripped[:limit]}..."
