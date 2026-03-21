from __future__ import annotations

import pytest

import use_anything.analyze.providers as providers
import use_anything.utils.tokens as tokens
from use_anything.exceptions import AnalyzeError


def test_extract_json_accepts_clean_json_object() -> None:
    payload = providers._extract_json('{"ok": true, "count": 1}')

    assert payload == {"ok": True, "count": 1}


def test_extract_json_recovers_from_prose_wrapped_response() -> None:
    text = "Here is the output:\n```json\n{\"ok\":true}\n```\nThanks!"

    payload = providers._extract_json(text)

    assert payload == {"ok": True}


@pytest.mark.fault_injection
def test_extract_json_rejects_missing_json_object() -> None:
    with pytest.raises(AnalyzeError, match="did not contain a JSON object"):
        providers._extract_json("no structured payload here")


def test_with_retry_retries_before_success(monkeypatch) -> None:
    attempts = {"count": 0}
    monkeypatch.setattr(providers.time, "sleep", lambda _: None)

    def flaky() -> str:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("transient")
        return "ok"

    assert providers._with_retry(flaky, retries=3) == "ok"
    assert attempts["count"] == 3


@pytest.mark.fault_injection
def test_with_retry_raises_analyze_error_after_exhausting_attempts(monkeypatch) -> None:
    monkeypatch.setattr(providers.time, "sleep", lambda _: None)

    def always_fail() -> str:
        raise RuntimeError("boom")

    with pytest.raises(AnalyzeError, match="failed after 2 attempts"):
        providers._with_retry(always_fail, retries=1)


def test_count_tokens_uses_fallback_estimate_when_tiktoken_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(tokens.tiktoken, "encoding_for_model", lambda model: (_ for _ in ()).throw(KeyError(model)))
    monkeypatch.setattr(tokens.tiktoken, "get_encoding", lambda name: (_ for _ in ()).throw(RuntimeError(name)))

    count = tokens.count_tokens("one two three", model="unknown-model")

    assert count == 3


def test_count_tokens_uses_encoding_when_available(monkeypatch) -> None:
    class DummyEncoding:
        def encode(self, text: str) -> list[int]:
            return [1] * len(text.split())

    monkeypatch.setattr(tokens.tiktoken, "encoding_for_model", lambda model: DummyEncoding())

    count = tokens.count_tokens("one two three", model="gpt-4.1")

    assert count == 3
