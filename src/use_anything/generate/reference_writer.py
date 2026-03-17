"""Reference file generation."""

from __future__ import annotations

from use_anything.models import AnalyzerIR


def build_api_reference(analysis: AnalyzerIR) -> str:
    lines = [f"# {analysis.software} API Reference", ""]
    for group in analysis.capability_groups:
        lines.append(f"## {group.name}")
        lines.append("")
        for capability in group.capabilities:
            lines.append(f"### {capability.name}")
            lines.append(f"- Function: `{capability.function}`")
            lines.append(f"- Returns: {capability.returns}")
            lines.append(f"- Notes: {capability.notes}")
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_workflows_reference(analysis: AnalyzerIR) -> str:
    lines = [f"# {analysis.software} Workflows", ""]
    for workflow in analysis.workflows:
        lines.append(f"## {workflow.name}")
        lines.append("")
        for step in workflow.steps:
            lines.append(step)
        if workflow.common_errors:
            lines.append("")
            lines.append("Common errors:")
            for error in workflow.common_errors:
                lines.append(f"- {error}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_gotchas_reference(analysis: AnalyzerIR) -> str:
    lines = [f"# {analysis.software} Gotchas", ""]
    for gotcha in analysis.gotchas:
        lines.append(f"- {gotcha}")
    return "\n".join(lines).strip() + "\n"
