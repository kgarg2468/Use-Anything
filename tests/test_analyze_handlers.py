from __future__ import annotations

from use_anything.analyze.interface_handlers import build_interface_context
from use_anything.models import InterfaceCandidate, ProbeResult


def test_build_interface_context_for_openapi_candidate() -> None:
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


def test_build_interface_context_for_cli_candidate() -> None:
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
