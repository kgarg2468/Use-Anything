"""Prompt templates for LLM-powered analysis."""

from __future__ import annotations

import json

from use_anything.models import ProbeResult, RankResult

SYSTEM_PROMPT = """You are Use-Anything, an expert at converting software interfaces into procedural agent skills.
Return only valid JSON matching the provided schema.
Prioritize concrete workflows and failure-preventing gotchas over exhaustive API enumeration.
"""
MAX_DISCOVERED_INTERFACE_LINES = 12
MAX_INTERFACE_CONTEXT_CHARS = 6000
MAX_INTERFACE_CONTEXT_CHARS_GITHUB = 2500
MAX_SUMMARY_CHARS = 800
MAX_SUMMARY_CHARS_GITHUB = 400
MAX_PROJECT_URLS_CHARS = 1200
MAX_PROJECT_URLS_CHARS_GITHUB = 500
MAX_CONTEXT_CLAIMS_CHARS = 1400


def build_analysis_prompt(
    *,
    probe_result: ProbeResult,
    rank_result: RankResult,
    interface_context: str,
    analysis_sources: list[str],
    context_claims: list[str] | None = None,
) -> str:
    """Build the user prompt for deep interface analysis."""

    metadata = probe_result.source_metadata
    is_github_target = probe_result.target_type == "github_repo"
    summary_limit = MAX_SUMMARY_CHARS_GITHUB if is_github_target else MAX_SUMMARY_CHARS
    project_urls_limit = MAX_PROJECT_URLS_CHARS_GITHUB if is_github_target else MAX_PROJECT_URLS_CHARS
    context_limit = MAX_INTERFACE_CONTEXT_CHARS_GITHUB if is_github_target else MAX_INTERFACE_CONTEXT_CHARS

    discovered = probe_result.interfaces_found[:MAX_DISCOVERED_INTERFACE_LINES]
    interfaces_text = "\n".join(
        f"- {candidate.type}: {candidate.location} (quality={candidate.quality_score})"
        for candidate in discovered
    )
    if len(probe_result.interfaces_found) > len(discovered):
        interfaces_text = (
            interfaces_text
            + "\n"
            + f"- ... {len(probe_result.interfaces_found) - len(discovered)} more interface candidates [truncated]"
        )
    project_urls_text = _truncate(
        json.dumps(metadata.get("project_urls", {}), sort_keys=True),
        project_urls_limit,
    )
    claims_text = _format_context_claims(context_claims or [])

    return (
        f"Target package: {probe_result.target}\n"
        f"Target type: {probe_result.target_type}\n"
        f"Preferred interface: {rank_result.primary.type}\n"
        f"Package version: {metadata.get('version', 'unknown')}\n"
        f"Summary: {_truncate(str(metadata.get('summary', '')), summary_limit)}\n"
        f"Project URLs: {project_urls_text}\n\n"
        "Discovered interfaces:\n"
        f"{interfaces_text}\n\n"
        "Interface-specific context:\n"
        f"{_truncate(interface_context, context_limit)}\n\n"
        "Curated context-doc claims:\n"
        f"{claims_text}\n\n"
        f"Analysis sources (must be included in output as analysis_sources): {analysis_sources}\n\n"
        "Generate a strict JSON object with setup, capability groups, workflows, and gotchas. "
        "Workflows must be procedural and include concrete steps and common errors. "
        "Do not invent commands/functions/endpoints that are absent from the provided context. "
        "Tie workflows and gotchas to provided evidence and prioritize reliable, executable steps. "
        "Include analysis_sources as a list of provenance strings. "
        "Also include gotcha_provenance as a list of objects with gotcha, source, evidence, and url."
    )


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[:limit]} [truncated]"


def _format_context_claims(claims: list[str]) -> str:
    if not claims:
        return "- none"
    rendered = "\n".join(f"- {claim}" for claim in claims[:25])
    return _truncate(rendered, MAX_CONTEXT_CLAIMS_CHARS)
