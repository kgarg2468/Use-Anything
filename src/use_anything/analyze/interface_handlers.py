"""Interface-specific context extraction for analyzer prompts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from use_anything.models import InterfaceCandidate, ProbeResult


@dataclass(frozen=True)
class InterfaceContext:
    summary: str
    sources: list[str]


def build_interface_context(*, probe_result: ProbeResult, interface_type: str) -> InterfaceContext:
    """Build interface-specific context for analysis prompts."""

    candidate = _select_candidate(probe_result.interfaces_found, interface_type)
    if candidate is None:
        return InterfaceContext(summary="No interface-specific context available.", sources=[])

    if interface_type == "openapi_spec":
        return _build_openapi_context(candidate)
    if interface_type == "cli_tool":
        return _build_cli_context(candidate, probe_result.source_metadata)

    return _build_generic_context(candidate, probe_result.source_metadata)


def _build_openapi_context(candidate: InterfaceCandidate) -> InterfaceContext:
    document = _load_openapi_document(candidate)
    if not document:
        return InterfaceContext(
            summary=f"OpenAPI interface located at {candidate.location}",
            sources=[f"openapi:{candidate.location}"],
        )

    info = document.get("info", {}) if isinstance(document, dict) else {}
    title = info.get("title", "Unknown API")
    version = info.get("version", "unknown")
    operations = _extract_openapi_operations(document)

    lines = [
        f"OpenAPI title: {title}",
        f"OpenAPI version: {version}",
        f"Discovered operations: {len(operations)}",
    ]
    if operations:
        lines.append("Operations sample:")
        lines.extend(f"- {operation}" for operation in operations[:15])

    return InterfaceContext(
        summary="\n".join(lines),
        sources=[f"openapi:{candidate.location}"],
    )


def _build_cli_context(candidate: InterfaceCandidate, source_metadata: dict[str, Any]) -> InterfaceContext:
    command_output = source_metadata.get("command_output", {}) if isinstance(source_metadata, dict) else {}
    help_text = str(candidate.metadata.get("help_text") or command_output.get("help") or "")
    version_text = str(candidate.metadata.get("version_text") or command_output.get("version") or "")

    lines = [f"CLI interface location: {candidate.location}"]
    if help_text:
        lines.append("Help output excerpt:")
        lines.append(help_text[:1200])
    if version_text:
        lines.append("Version output excerpt:")
        lines.append(version_text[:400])

    return InterfaceContext(
        summary="\n".join(lines),
        sources=[f"cli:{candidate.location}"],
    )


def _build_generic_context(candidate: InterfaceCandidate, source_metadata: dict[str, Any]) -> InterfaceContext:
    summary = str(source_metadata.get("summary", ""))
    project_urls = source_metadata.get("project_urls", {})
    lines = [
        f"Interface type: {candidate.type}",
        f"Interface location: {candidate.location}",
    ]
    if summary:
        lines.append(f"Package summary: {summary}")
    if project_urls:
        lines.append(f"Project URLs: {project_urls}")

    return InterfaceContext(
        summary="\n".join(lines),
        sources=[f"{candidate.type}:{candidate.location}"],
    )


def _select_candidate(candidates: list[InterfaceCandidate], interface_type: str) -> InterfaceCandidate | None:
    for candidate in candidates:
        if candidate.type == interface_type:
            return candidate
    return candidates[0] if candidates else None


def _load_openapi_document(candidate: InterfaceCandidate) -> dict[str, Any]:
    raw = candidate.metadata.get("openapi_document")
    if isinstance(raw, dict):
        return raw

    path = Path(candidate.location)
    if not path.exists() or not path.is_file():
        return {}

    content = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        try:
            loaded = json.loads(content)
        except json.JSONDecodeError:
            return {}
        return loaded if isinstance(loaded, dict) else {}

    try:
        loaded_yaml = yaml.safe_load(content)
    except yaml.YAMLError:
        return {}

    return loaded_yaml if isinstance(loaded_yaml, dict) else {}


def _extract_openapi_operations(document: dict[str, Any]) -> list[str]:
    paths = document.get("paths", {})
    if not isinstance(paths, dict):
        return []

    operations: list[str] = []
    for path, methods in paths.items():
        if not isinstance(methods, dict):
            continue
        for method in methods:
            upper = str(method).upper()
            if upper in {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}:
                operations.append(f"{upper} {path}")
    return operations
