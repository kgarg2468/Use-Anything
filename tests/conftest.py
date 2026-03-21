from __future__ import annotations

from pathlib import Path

import pytest


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
