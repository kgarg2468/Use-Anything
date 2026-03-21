from __future__ import annotations

import subprocess
import sys
import types
from pathlib import Path

import pytest

from use_anything.analyze.llm_client import LLMClient
from use_anything.analyze.providers import AnthropicProvider, CodexCLIProvider, OpenAIProvider
from use_anything.exceptions import AnalyzeError


def _schema() -> dict:
    return {
        "type": "object",
        "properties": {"ok": {"type": "boolean"}},
        "required": ["ok"],
    }


def test_llmclient_selects_codex_cli_provider(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    client = LLMClient(model="codex-cli")

    assert isinstance(client._provider, CodexCLIProvider)
    assert client._provider.timeout_seconds == 60
    assert client._provider.max_retries == 2


def test_llmclient_allows_codex_timeout_and_retry_overrides(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    client = LLMClient(model="codex-cli", timeout_seconds=600, max_retries=1)

    assert isinstance(client._provider, CodexCLIProvider)
    assert client._provider.timeout_seconds == 600
    assert client._provider.max_retries == 1


def test_llmclient_error_mentions_codex_option_when_no_keys(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(AnalyzeError, match="codex-cli"):
        LLMClient()


def test_llmclient_requires_openai_key_for_openai_models(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(AnalyzeError, match="OPENAI_API_KEY"):
        LLMClient(model="gpt-4.1")


def test_llmclient_prefers_anthropic_provider_when_key_exists(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    client = LLMClient(model="claude-sonnet-4-6")

    assert isinstance(client._provider, AnthropicProvider)


def test_llmclient_falls_back_to_openai_when_only_openai_key_exists(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")

    client = LLMClient(model=None)

    assert isinstance(client._provider, OpenAIProvider)


def test_llmclient_rejects_unknown_model_without_keys(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(AnalyzeError, match="No API key configured"):
        LLMClient(model="unknown-provider")


def test_codex_provider_missing_binary(monkeypatch) -> None:
    provider = CodexCLIProvider(timeout_seconds=5, max_retries=0)
    monkeypatch.setattr("use_anything.analyze.providers.shutil.which", lambda _: None)

    with pytest.raises(AnalyzeError, match="codex CLI executable not found"):
        provider.complete_json(system_prompt="system", user_prompt="prompt", schema=_schema())


def test_codex_provider_non_zero_exit(monkeypatch) -> None:
    provider = CodexCLIProvider(timeout_seconds=5, max_retries=0)
    monkeypatch.setattr("use_anything.analyze.providers.shutil.which", lambda _: "/usr/bin/codex")

    def fake_run(*args, **kwargs):  # noqa: ANN002, ANN003
        return subprocess.CompletedProcess(args=args[0], returncode=1, stdout="", stderr="auth failed")

    monkeypatch.setattr("use_anything.analyze.providers.subprocess.run", fake_run)

    with pytest.raises(AnalyzeError, match="codex exec failed"):
        provider.complete_json(system_prompt="system", user_prompt="prompt", schema=_schema())


def test_codex_provider_timeout(monkeypatch) -> None:
    provider = CodexCLIProvider(timeout_seconds=1, max_retries=0)
    monkeypatch.setattr("use_anything.analyze.providers.shutil.which", lambda _: "/usr/bin/codex")

    def fake_run(*args, **kwargs):  # noqa: ANN002, ANN003
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=1)

    monkeypatch.setattr("use_anything.analyze.providers.subprocess.run", fake_run)

    with pytest.raises(AnalyzeError, match="timed out"):
        provider.complete_json(system_prompt="system", user_prompt="prompt", schema=_schema())


def test_codex_provider_reads_and_parses_last_message(monkeypatch) -> None:
    provider = CodexCLIProvider(timeout_seconds=5, max_retries=0)
    monkeypatch.setattr("use_anything.analyze.providers.shutil.which", lambda _: "/usr/bin/codex")

    def fake_run(command, **kwargs):  # noqa: ANN001, ANN003
        assert "--sandbox" in command
        assert "read-only" in command
        output_index = command.index("--output-last-message") + 1
        output_file = Path(command[output_index])
        output_file.write_text('{"ok": true}')
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("use_anything.analyze.providers.subprocess.run", fake_run)

    payload = provider.complete_json(system_prompt="system", user_prompt="prompt", schema=_schema())

    assert payload == {"ok": True}


def test_codex_provider_rejects_non_json_last_message(monkeypatch) -> None:
    provider = CodexCLIProvider(timeout_seconds=5, max_retries=0)
    monkeypatch.setattr("use_anything.analyze.providers.shutil.which", lambda _: "/usr/bin/codex")

    def fake_run(command, **kwargs):  # noqa: ANN001, ANN003
        output_index = command.index("--output-last-message") + 1
        output_file = Path(command[output_index])
        output_file.write_text("not-json")
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("use_anything.analyze.providers.subprocess.run", fake_run)

    with pytest.raises(AnalyzeError, match="JSON"):
        provider.complete_json(system_prompt="system", user_prompt="prompt", schema=_schema())


def test_anthropic_provider_parses_json_response(monkeypatch) -> None:
    class FakeAnthropicClient:
        def __init__(self, api_key: str, timeout: int) -> None:  # noqa: ARG002
            self.messages = self

        def create(self, **kwargs):  # noqa: ANN003, ARG002
            text_block = types.SimpleNamespace(type="text", text='{"ok": true, "source": "anthropic"}')
            return types.SimpleNamespace(content=[text_block])

    fake_module = types.SimpleNamespace(Anthropic=FakeAnthropicClient)
    monkeypatch.setitem(sys.modules, "anthropic", fake_module)

    provider = AnthropicProvider(api_key="test", model="claude-sonnet-4-6", timeout_seconds=5, max_retries=0)
    payload = provider.complete_json(system_prompt="sys", user_prompt="user", schema=_schema())

    assert payload == {"ok": True, "source": "anthropic"}


def test_openai_provider_parses_json_response(monkeypatch) -> None:
    class FakeOpenAIClient:
        def __init__(self, api_key: str, timeout: int) -> None:  # noqa: ARG002
            self.chat = types.SimpleNamespace(completions=self)

        def create(self, **kwargs):  # noqa: ANN003, ARG002
            message = types.SimpleNamespace(content='{"ok": true, "source": "openai"}')
            choice = types.SimpleNamespace(message=message)
            return types.SimpleNamespace(choices=[choice])

    fake_module = types.SimpleNamespace(OpenAI=FakeOpenAIClient)
    monkeypatch.setitem(sys.modules, "openai", fake_module)

    provider = OpenAIProvider(api_key="test", model="gpt-4.1", timeout_seconds=5, max_retries=0)
    payload = provider.complete_json(system_prompt="sys", user_prompt="user", schema=_schema())

    assert payload == {"ok": True, "source": "openai"}
