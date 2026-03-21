from __future__ import annotations

import os

import httpx
import pytest

from use_anything.analyze.providers import OpenAIProvider
from use_anything.probe.pypi import fetch_pypi_metadata

RUN_LIVE_SMOKE = os.getenv("USE_ANYTHING_RUN_LIVE_SMOKE", "0") == "1"
RUN_LIVE_LLM = os.getenv("USE_ANYTHING_RUN_LIVE_SMOKE_LLM", "0") == "1"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()


@pytest.mark.live_smoke
@pytest.mark.skipif(not RUN_LIVE_SMOKE, reason="set USE_ANYTHING_RUN_LIVE_SMOKE=1 to run live smoke checks")
def test_live_smoke_pypi_metadata_fetch_requests() -> None:
    payload = fetch_pypi_metadata("requests", timeout=15.0)

    assert payload["info"]["name"].lower() == "requests"
    assert payload["info"]["version"]


@pytest.mark.live_smoke
@pytest.mark.skipif(not RUN_LIVE_SMOKE, reason="set USE_ANYTHING_RUN_LIVE_SMOKE=1 to run live smoke checks")
def test_live_smoke_github_repo_metadata() -> None:
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    response = httpx.get("https://api.github.com/repos/psf/requests", headers=headers, timeout=15.0)
    response.raise_for_status()
    payload = response.json()

    assert payload["name"].lower() == "requests"
    assert payload["full_name"].lower() == "psf/requests"


@pytest.mark.live_smoke
@pytest.mark.skipif(not RUN_LIVE_SMOKE, reason="set USE_ANYTHING_RUN_LIVE_SMOKE=1 to run live smoke checks")
@pytest.mark.skipif(not RUN_LIVE_LLM, reason="set USE_ANYTHING_RUN_LIVE_SMOKE_LLM=1 to include live LLM call")
@pytest.mark.skipif(not OPENAI_API_KEY, reason="OPENAI_API_KEY is required for live LLM smoke test")
def test_live_smoke_openai_provider_json_completion() -> None:
    provider = OpenAIProvider(api_key=OPENAI_API_KEY, model="gpt-4.1-mini", timeout_seconds=40, max_retries=0)
    payload = provider.complete_json(
        system_prompt="Return strict JSON",
        user_prompt="Return object with ok=true and source='live-smoke'",
        schema={
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "source": {"type": "string"},
            },
            "required": ["ok", "source"],
        },
    )

    assert payload["ok"] is True
    assert isinstance(payload["source"], str)
