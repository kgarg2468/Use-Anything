"""Interface-specific context extraction for analyzer prompts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import yaml

from use_anything.analyze.evidence import GotchaEvidenceEntry, mine_gotcha_evidence
from use_anything.models import InterfaceCandidate, ProbeResult

MAX_SOURCE_EXCERPT_CHARS = 600
MAX_DESCRIPTION_CHARS = 1200


@dataclass(frozen=True)
class InterfaceContext:
    summary: str
    sources: list[str]
    gotcha_evidence: list[GotchaEvidenceEntry] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def build_interface_context(*, probe_result: ProbeResult, interface_type: str) -> InterfaceContext:
    """Build interface-specific context for analysis prompts."""

    candidate = _select_candidate(probe_result.interfaces_found, interface_type)
    if candidate is None:
        return InterfaceContext(summary="No interface-specific context available.", sources=[])

    evidence_result = mine_gotcha_evidence(probe_result)
    prioritized_sources = _prioritized_support_sources(probe_result.interfaces_found)
    if interface_type == "openapi_spec":
        context = _build_openapi_context(candidate)
    elif interface_type == "cli_tool":
        context = _build_cli_context(candidate, probe_result.source_metadata)
    else:
        context = _build_generic_context(candidate, probe_result.source_metadata)

    summary_parts: list[str] = []
    code_signal_lines = _render_context_code_signals(probe_result.source_metadata)
    if code_signal_lines:
        summary_parts.append("Local code signals (highest precedence):")
        summary_parts.extend(code_signal_lines)

    summary_parts.append(context.summary)

    if prioritized_sources:
        summary_parts.append("Supplemental prioritized sources:")
        summary_parts.extend(f"- {source}" for source in prioritized_sources)

    source_excerpts = _collect_source_excerpts(candidate, probe_result.source_metadata)
    if source_excerpts:
        summary_parts.append("Source excerpts:")
        summary_parts.extend(f"- {excerpt}" for excerpt in source_excerpts)

    if evidence_result.entries:
        summary_parts.append("Gotcha evidence (external sources):")
        summary_parts.extend(_render_gotcha_evidence_line(entry) for entry in evidence_result.entries)

    context_claim_lines = _render_context_doc_claims(probe_result.source_metadata)
    if context_claim_lines:
        summary_parts.append("Context doc claims (lowest precedence; use only when code agrees):")
        summary_parts.extend(context_claim_lines)

    summary = "\n".join(summary_parts)

    evidence_sources = [entry.source_ref() for entry in evidence_result.entries]
    merged_sources = _dedupe_sources([*prioritized_sources, *context.sources, *evidence_sources])
    return InterfaceContext(
        summary=summary,
        sources=merged_sources,
        gotcha_evidence=evidence_result.entries,
        warnings=evidence_result.warnings,
    )


def _prioritized_support_sources(candidates: list[InterfaceCandidate]) -> list[str]:
    sources: list[str] = []
    for interface_type in ("llms_txt", "existing_skill"):
        for candidate in candidates:
            if candidate.type == interface_type:
                sources.append(f"{interface_type}:{candidate.location}")
    return _dedupe_sources(sources)


def _dedupe_sources(sources: list[str]) -> list[str]:
    deduped: list[str] = []
    for source in sources:
        if source not in deduped:
            deduped.append(source)
    return deduped


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

    location = candidate.location
    if location.startswith("http://") or location.startswith("https://"):
        return _load_openapi_from_http(location)

    path = Path(location)
    if not path.exists() or not path.is_file():
        return {}

    content = path.read_text(encoding="utf-8")
    return _parse_openapi_content(content, path.suffix.lower())


def _load_openapi_from_http(location: str) -> dict[str, Any]:
    try:
        response = httpx.get(location, timeout=15.0)
        response.raise_for_status()
    except httpx.HTTPError:
        return {}

    content_type = response.headers.get("content-type", "").lower()
    suffix = ".json" if "json" in content_type else ".yaml"
    return _parse_openapi_content(response.text, suffix)


def _parse_openapi_content(content: str, suffix: str) -> dict[str, Any]:
    if suffix == ".json":
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


def _collect_source_excerpts(candidate: InterfaceCandidate, source_metadata: dict[str, Any]) -> list[str]:
    excerpts: list[str] = []

    summary = _truncate_text(str(source_metadata.get("summary", "")), MAX_SOURCE_EXCERPT_CHARS)
    description = _truncate_text(str(source_metadata.get("description", "")), MAX_DESCRIPTION_CHARS)
    candidate_excerpt = _truncate_text(str(candidate.metadata.get("evidence_excerpt", "")), MAX_SOURCE_EXCERPT_CHARS)

    if summary:
        excerpts.append(f"metadata.summary: {summary}")
    if description:
        excerpts.append(f"metadata.description: {description}")
    if candidate_excerpt:
        excerpts.append(f"candidate.metadata.evidence_excerpt: {candidate_excerpt}")

    command_output = source_metadata.get("command_output", {}) if isinstance(source_metadata, dict) else {}
    help_text = _truncate_text(str(command_output.get("help", "")), MAX_SOURCE_EXCERPT_CHARS)
    version_text = _truncate_text(str(command_output.get("version", "")), MAX_SOURCE_EXCERPT_CHARS)

    if help_text:
        excerpts.append(f"command_output.help: {help_text}")
    if version_text:
        excerpts.append(f"command_output.version: {version_text}")

    return excerpts


def _truncate_text(value: str, limit: int) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        return ""
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]} [truncated]"


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


def _render_gotcha_evidence_line(entry: GotchaEvidenceEntry) -> str:
    return (
        f"- [{entry.category}] {entry.title} "
        f"(source={entry.source_label}; score={entry.relevance_score}; url={entry.url})"
    )


def _render_context_code_signals(source_metadata: dict[str, Any]) -> list[str]:
    raw = source_metadata.get("context_code_signals")
    if not isinstance(raw, list):
        return []
    output: list[str] = []
    for item in raw[:25]:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind", "")).strip()
        path = str(item.get("path", "")).strip()
        value = str(item.get("value", "")).strip()
        if not kind:
            continue
        descriptor = f"- {kind}"
        if value:
            descriptor += f"={value}"
        if path:
            descriptor += f" ({path})"
        output.append(descriptor)
    return output


def _render_context_doc_claims(source_metadata: dict[str, Any]) -> list[str]:
    raw = source_metadata.get("context_doc_claims")
    if not isinstance(raw, list):
        return []
    output: list[str] = []
    for item in raw[:20]:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        source_path = str(item.get("source_path", "")).strip()
        source_section = str(item.get("source_section", "")).strip()
        if not text:
            continue
        source_label = source_path or "context-doc"
        if source_section:
            source_label = f"{source_label}#{source_section}"
        output.append(f"- [{source_label}] {text}")
    return output
