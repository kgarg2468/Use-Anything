from __future__ import annotations

import use_anything.probe.adapters as adapters
from use_anything.probe.adapters import probe_docs_url
from use_anything.probe.interface_scanner import discover_interface_candidates


def test_discover_interface_candidates_from_paths() -> None:
    candidates = discover_interface_candidates(
        source_location="https://example.dev",
        paths=[
            "docs/openapi.yaml",
            "docs/llms.txt",
            ".well-known/skills/default/skill.md",
        ],
    )

    types = {candidate.type for candidate in candidates}
    assert "openapi_spec" in types
    assert "llms_txt" in types
    assert "existing_skill" in types


def test_probe_docs_url_does_not_emit_unverified_preflight_candidates(monkeypatch) -> None:
    monkeypatch.setattr(adapters, "_fetch_url", lambda url, timeout=15.0: (404, "text/plain", ""))

    candidates, _ = probe_docs_url("https://docs.example.dev", html="<html><body>No links</body></html>")

    types = {candidate.type for candidate in candidates}
    assert "openapi_spec" not in types
    assert "llms_txt" not in types


def test_discover_interface_candidates_avoids_rest_doc_false_positive_from_code_paths() -> None:
    candidates = discover_interface_candidates(
        source_location="/tmp/repo",
        paths=[
            "pyproject.toml",
            "src/use_anything/generate/reference_writer.py",
        ],
    )

    types = {candidate.type for candidate in candidates}
    assert "python_sdk" in types
    assert "rest_api_docs" not in types
