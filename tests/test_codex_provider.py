from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from use_anything.analyze.llm_client import LLMClient
from use_anything.analyze.providers import CodexCLIProvider
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


def test_llmclient_error_mentions_codex_option_when_no_keys(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(AnalyzeError, match="codex-cli"):
        LLMClient()


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
