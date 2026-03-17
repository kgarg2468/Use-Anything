from __future__ import annotations

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


def test_probe_docs_url_uses_preflight_paths_when_html_has_no_links() -> None:
    candidates, _ = probe_docs_url("https://docs.example.dev", html="<html><body>No links</body></html>")

    types = {candidate.type for candidate in candidates}
    assert "openapi_spec" in types
    assert "llms_txt" in types

    openapi_candidate = next(candidate for candidate in candidates if candidate.type == "openapi_spec")
    assert openapi_candidate.location.endswith("/openapi.json")
