"""Prompt templates for LLM-powered analysis."""

from __future__ import annotations

from use_anything.models import ProbeResult, RankResult

SYSTEM_PROMPT = """You are Use-Anything, an expert at converting software interfaces into procedural agent skills.
Return only valid JSON matching the provided schema.
Prioritize concrete workflows and failure-preventing gotchas over exhaustive API enumeration.
"""


def build_analysis_prompt(*, probe_result: ProbeResult, rank_result: RankResult) -> str:
    """Build the user prompt for deep interface analysis."""

    metadata = probe_result.source_metadata
    interfaces_text = "\n".join(
        f"- {candidate.type}: {candidate.location} (quality={candidate.quality_score})"
        for candidate in probe_result.interfaces_found
    )

    return (
        f"Target package: {probe_result.target}\n"
        f"Target type: {probe_result.target_type}\n"
        f"Preferred interface: {rank_result.primary.type}\n"
        f"Package version: {metadata.get('version', 'unknown')}\n"
        f"Summary: {metadata.get('summary', '')}\n"
        f"Project URLs: {metadata.get('project_urls', {})}\n\n"
        "Discovered interfaces:\n"
        f"{interfaces_text}\n\n"
        "Generate a strict JSON object with setup, capability groups, workflows, and gotchas. "
        "Workflows must be procedural and include concrete steps and common errors."
    )
