from __future__ import annotations

import use_anything.analyze.interface_handlers as interface_handlers
from use_anything.analyze.evidence import GotchaEvidenceEntry, GotchaEvidenceResult
from use_anything.analyze.interface_handlers import build_interface_context
from use_anything.models import InterfaceCandidate, ProbeResult


def test_build_interface_context_for_openapi_candidate(monkeypatch) -> None:
    monkeypatch.setattr(
        interface_handlers,
        "mine_gotcha_evidence",
        lambda probe_result: GotchaEvidenceResult(entries=[], warnings=[]),  # noqa: ARG005
    )
    probe_result = ProbeResult(
        target="demo",
        target_type="docs_url",
        interfaces_found=[
            InterfaceCandidate(
                type="openapi_spec",
                location="https://docs.example.dev/openapi.json",
                quality_score=0.95,
                coverage="full",
                notes="OpenAPI",
                metadata={
                    "openapi_document": {
                        "openapi": "3.0.0",
                        "info": {"title": "Demo API", "version": "1.2.3"},
                        "paths": {
                            "/users": {"get": {}, "post": {}},
                            "/projects": {"get": {}},
                        },
                    }
                },
            )
        ],
    )

    context = build_interface_context(probe_result=probe_result, interface_type="openapi_spec")

    assert "Demo API" in context.summary
    assert "GET /users" in context.summary
    assert "POST /users" in context.summary
    assert context.sources == ["openapi:https://docs.example.dev/openapi.json"]


def test_build_interface_context_for_cli_candidate(monkeypatch) -> None:
    monkeypatch.setattr(
        interface_handlers,
        "mine_gotcha_evidence",
        lambda probe_result: GotchaEvidenceResult(entries=[], warnings=[]),  # noqa: ARG005
    )
    probe_result = ProbeResult(
        target="ffmpeg",
        target_type="binary",
        interfaces_found=[
            InterfaceCandidate(
                type="cli_tool",
                location="binary:ffmpeg",
                quality_score=0.8,
                coverage="partial",
                notes="CLI",
                metadata={"help_text": "usage: ffmpeg -i input output"},
            )
        ],
        source_metadata={
            "command_output": {
                "help": "usage: ffmpeg -i input output",
                "version": "ffmpeg version 7.1",
            }
        },
    )

    context = build_interface_context(probe_result=probe_result, interface_type="cli_tool")

    assert "ffmpeg -i input output" in context.summary
    assert "version 7.1" in context.summary
    assert context.sources == ["cli:binary:ffmpeg"]


def test_build_interface_context_prioritizes_llms_and_existing_skill_sources() -> None:
    probe_result = ProbeResult(
        target="requests",
        target_type="docs_url",
        interfaces_found=[
            InterfaceCandidate(
                type="python_sdk",
                location="pypi:requests",
                quality_score=0.95,
                coverage="full",
                notes="sdk",
            ),
            InterfaceCandidate(
                type="llms_txt",
                location="https://docs.example.dev/llms.txt",
                quality_score=0.8,
                coverage="partial",
                notes="llms",
            ),
            InterfaceCandidate(
                type="existing_skill",
                location="https://docs.example.dev/skill.md",
                quality_score=0.8,
                coverage="partial",
                notes="skill",
            ),
        ],
        source_metadata={"summary": "HTTP helpers"},
    )

    context = build_interface_context(probe_result=probe_result, interface_type="python_sdk")

    assert context.sources[0] == "llms_txt:https://docs.example.dev/llms.txt"
    assert context.sources[1] == "existing_skill:https://docs.example.dev/skill.md"
    assert "Supplemental prioritized sources" in context.summary


def test_build_interface_context_loads_remote_openapi_document(monkeypatch) -> None:
    class FakeResponse:
        status_code = 200
        headers = {"content-type": "application/json"}
        text = '{"openapi":"3.1.0","info":{"title":"Remote Demo","version":"9.9.9"},"paths":{"/items":{"get":{}}}}'

        def raise_for_status(self) -> None:
            return None

    monkeypatch.setattr(interface_handlers.httpx, "get", lambda url, timeout=15.0: FakeResponse())  # noqa: ARG005
    monkeypatch.setattr(
        interface_handlers,
        "mine_gotcha_evidence",
        lambda probe_result: GotchaEvidenceResult(entries=[], warnings=[]),  # noqa: ARG005
    )

    probe_result = ProbeResult(
        target="demo",
        target_type="docs_url",
        interfaces_found=[
            InterfaceCandidate(
                type="openapi_spec",
                location="https://docs.example.dev/openapi.json",
                quality_score=0.95,
                coverage="full",
                notes="OpenAPI",
            )
        ],
    )

    context = build_interface_context(probe_result=probe_result, interface_type="openapi_spec")

    assert "Remote Demo" in context.summary
    assert "GET /items" in context.summary


def test_build_interface_context_adds_bounded_source_excerpts() -> None:
    long_description = " ".join(f"token-{index}" for index in range(700))
    probe_result = ProbeResult(
        target="requests",
        target_type="pypi_package",
        interfaces_found=[
            InterfaceCandidate(
                type="python_sdk",
                location="pypi:requests",
                quality_score=0.95,
                coverage="full",
                notes="sdk",
                metadata={"evidence_excerpt": "Short evidence excerpt"},
            )
        ],
        source_metadata={
            "summary": "HTTP helpers",
            "description": long_description,
        },
    )

    context = build_interface_context(probe_result=probe_result, interface_type="python_sdk")

    assert "Source excerpts" in context.summary
    assert "metadata.summary" in context.summary
    assert "[truncated]" in context.summary


def test_build_interface_context_includes_github_issue_evidence(monkeypatch) -> None:
    monkeypatch.setattr(
        interface_handlers,
        "mine_gotcha_evidence",
        lambda probe_result: GotchaEvidenceResult(  # noqa: ARG005
            entries=[
                GotchaEvidenceEntry(
                    source_type="github_issue",
                    source_label="github:org/repo#12",
                    url="https://github.com/org/repo/issues/12",
                    title="Auth token expires unexpectedly",
                    excerpt="401 errors happen after 60 minutes unless token refresh is enabled.",
                    category="auth",
                    relevance_score=0.92,
                )
            ],
            warnings=[],
        ),
    )

    probe_result = ProbeResult(
        target="requests",
        target_type="pypi_package",
        interfaces_found=[
            InterfaceCandidate(
                type="python_sdk",
                location="pypi:requests",
                quality_score=0.95,
                coverage="full",
                notes="sdk",
            )
        ],
        source_metadata={"summary": "HTTP helpers"},
    )

    context = build_interface_context(probe_result=probe_result, interface_type="python_sdk")

    assert "Gotcha evidence" in context.summary
    assert "Auth token expires unexpectedly" in context.summary
    assert "github_issue:https://github.com/org/repo/issues/12" in context.sources


def test_build_interface_context_includes_stackoverflow_evidence(monkeypatch) -> None:
    monkeypatch.setattr(
        interface_handlers,
        "mine_gotcha_evidence",
        lambda probe_result: GotchaEvidenceResult(  # noqa: ARG005
            entries=[
                GotchaEvidenceEntry(
                    source_type="stackoverflow",
                    source_label="stackoverflow:12345",
                    url="https://stackoverflow.com/questions/12345/example",
                    title="Rate limit retries cause duplicate requests",
                    excerpt="Use exponential backoff and idempotency keys.",
                    category="rate_limit",
                    relevance_score=0.88,
                )
            ],
            warnings=[],
        ),
    )

    probe_result = ProbeResult(
        target="requests",
        target_type="pypi_package",
        interfaces_found=[
            InterfaceCandidate(
                type="python_sdk",
                location="pypi:requests",
                quality_score=0.95,
                coverage="full",
                notes="sdk",
            )
        ],
        source_metadata={"summary": "HTTP helpers"},
    )

    context = build_interface_context(probe_result=probe_result, interface_type="python_sdk")

    assert "Rate limit retries cause duplicate requests" in context.summary
    assert "stackoverflow:https://stackoverflow.com/questions/12345/example" in context.sources


def test_build_interface_context_surfaces_evidence_warnings(monkeypatch) -> None:
    monkeypatch.setattr(
        interface_handlers,
        "mine_gotcha_evidence",
        lambda probe_result: GotchaEvidenceResult(  # noqa: ARG005
            entries=[],
            warnings=["GitHub issue evidence unavailable: API rate limited"],
        ),
    )

    probe_result = ProbeResult(
        target="requests",
        target_type="pypi_package",
        interfaces_found=[
            InterfaceCandidate(
                type="python_sdk",
                location="pypi:requests",
                quality_score=0.95,
                coverage="full",
                notes="sdk",
            )
        ],
        source_metadata={"summary": "HTTP helpers"},
    )

    context = build_interface_context(probe_result=probe_result, interface_type="python_sdk")

    assert context.warnings == ["GitHub issue evidence unavailable: API rate limited"]
