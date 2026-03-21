from __future__ import annotations

from pathlib import Path

import pytest

from use_anything.models import AnalyzerIR, GeneratedArtifacts


@pytest.fixture()
def sample_analysis_dict() -> dict:
    return {
        "software": "requests",
        "interface": "python_sdk",
        "version": "2.32.3",
        "setup": {
            "install": "pip install requests",
            "auth": "No auth required for the library itself",
            "env_vars": [],
            "prerequisites": ["Python 3.10+"],
        },
        "capability_groups": [
            {
                "name": "HTTP requests",
                "capabilities": [
                    {
                        "name": "GET request",
                        "function": "requests.get(url, params=None, timeout=30)",
                        "params": {"url": "str", "params": "dict[str, str] | None"},
                        "returns": "requests.Response",
                        "notes": "Call response.raise_for_status() for non-2xx errors.",
                    },
                    {
                        "name": "POST JSON",
                        "function": "requests.post(url, json=payload, timeout=30)",
                        "params": {"url": "str", "json": "dict[str, object]"},
                        "returns": "requests.Response",
                        "notes": "Use json=, not data=, for JSON encoding.",
                    },
                ],
            }
        ],
        "workflows": [
            {
                "name": "Fetch JSON data",
                "steps": [
                    "1. Call requests.get(url, timeout=30)",
                    "2. Call response.raise_for_status()",
                    "3. Parse response.json()",
                ],
                "common_errors": ["Forgetting timeout argument can hang indefinitely"],
            },
            {
                "name": "Submit JSON payload",
                "steps": [
                    "1. Build payload dict",
                    "2. Call requests.post(url, json=payload, timeout=30)",
                    "3. Validate response.status_code",
                ],
                "common_errors": ["Using data= for JSON payloads"],
            },
            {
                "name": "Retry transient failures",
                "steps": [
                    "1. Create Session()",
                    "2. Configure HTTPAdapter with retries",
                    "3. Use session.get() for requests",
                ],
                "common_errors": ["Retries not configured for both http and https"],
            },
        ],
        "gotchas": [
            "Always pass timeout to avoid hanging requests.",
            "response.json() raises if the body is not valid JSON.",
            "Use response.raise_for_status() before parsing body.",
            "Session objects are not inherently thread-safe.",
            "Retries require urllib3 Retry + mounted adapter.",
        ],
        "analysis_sources": [
            "python_sdk:pypi:requests",
            "docs:https://requests.readthedocs.io/en/latest/",
        ],
        "gotcha_provenance": [
            {
                "gotcha": "Always pass timeout to avoid hanging requests.",
                "source": "docs:https://requests.readthedocs.io/en/latest/user/quickstart/",
                "evidence": "Requests can block indefinitely without explicit timeout.",
                "url": "https://requests.readthedocs.io/en/latest/user/quickstart/",
            }
        ],
    }


@pytest.fixture()
def tmp_skill_dir(tmp_path: Path) -> Path:
    skill_dir = tmp_path / "use-anything-requests"
    skill_dir.mkdir(parents=True, exist_ok=True)
    return skill_dir


@pytest.fixture()
def deterministic_time(monkeypatch) -> list[float]:
    """Provide deterministic time.perf_counter values for duration assertions."""

    values = [1.0, 1.015, 1.03, 1.05, 1.08]
    state = {"idx": -1}

    def fake_perf_counter() -> float:
        state["idx"] += 1
        if state["idx"] >= len(values):
            return values[-1]
        return values[state["idx"]]

    monkeypatch.setattr("time.perf_counter", fake_perf_counter)
    return values


@pytest.fixture()
def minimal_analysis_ir() -> AnalyzerIR:
    return AnalyzerIR.from_dict(
        {
            "software": "demo",
            "interface": "python_sdk",
            "version": "1.0.0",
            "setup": {
                "install": "pip install demo",
                "auth": "Set DEMO_API_KEY",
                "env_vars": ["DEMO_API_KEY"],
                "prerequisites": ["Python 3.10+"],
            },
            "capability_groups": [],
            "workflows": [
                {
                    "name": "Quickstart",
                    "steps": ["python -c \"print('ok')\""],
                    "common_errors": [],
                }
            ],
            "gotchas": ["Set timeout defaults"],
            "analysis_sources": ["python_sdk:pypi:demo"],
        }
    )


@pytest.fixture()
def generated_artifacts_with_verify_script(tmp_path: Path) -> GeneratedArtifacts:
    script_path = tmp_path / "scripts" / "verify_setup.py"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text("print('verify')\n", encoding="utf-8")
    return GeneratedArtifacts(
        skill_path=tmp_path / "SKILL.md",
        reference_paths={},
        token_counts={},
        line_counts={},
        script_paths={"verify_setup": script_path},
    )
