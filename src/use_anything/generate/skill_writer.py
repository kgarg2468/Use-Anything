"""Main SKILL.md renderer."""

from __future__ import annotations

import re
from datetime import date

import yaml

from use_anything.models import AnalyzerIR, Workflow

DEFAULT_GOTCHAS = [
    "Always verify installation and import before running workflows.",
    "Prefer explicit timeouts or retries for network-bound operations.",
    "Validate returned object fields before using downstream values.",
    "Pin package versions when reproducibility matters.",
    "Handle authentication and permission errors explicitly.",
]


def render_skill_markdown(analysis: AnalyzerIR, *, source_interface: str) -> str:
    """Render SKILL.md from analysis IR."""

    name = _slugify(analysis.software)
    workflows = _ensure_workflow_count(analysis.workflows, analysis.capability_groups)
    gotchas = _ensure_gotcha_count(analysis.gotchas)
    quick_reference = _build_quick_reference(analysis)
    description = _build_description(analysis)

    frontmatter = {
        "name": name,
        "description": description,
        "license": "MIT",
        "metadata": {
            "author": "use-anything",
            "version": "1.0",
            "generated_by": "use-anything",
            "source_interface": source_interface,
            "software_version": analysis.version,
            "generated_date": date.today().isoformat(),
        },
    }

    body_lines = [
        f"# {analysis.software}",
        "",
        f"Use this skill to work with {analysis.software} through the {analysis.interface} interface.",
        "",
        "## Setup",
        "",
        analysis.setup.install or "Install command not provided.",
        "",
        analysis.setup.auth or "Auth details were not provided by source docs.",
        "",
        "## Key concepts",
        "",
    ]

    key_concepts = _extract_key_concepts(analysis)
    body_lines.extend(f"- {item}" for item in key_concepts)

    body_lines.extend(["", "## Core workflows", ""])
    for workflow in workflows:
        body_lines.extend(_render_workflow(workflow))

    body_lines.extend(["", "## Important constraints", ""])
    body_lines.extend(f"- {gotcha}" for gotcha in gotchas)

    body_lines.extend(["", "## Quick reference", ""])
    body_lines.extend([
        "| Operation | Command or Function |",
        "|---|---|",
    ])
    for operation, command in quick_reference:
        body_lines.append(f"| {operation} | `{command}` |")

    body_lines.extend(
        [
            "",
            "## When to use references",
            "",
            "For complete function coverage see `references/API_REFERENCE.md`. "
            "For expanded procedures see `references/WORKFLOWS.md`. "
            "For edge-case warnings see `references/GOTCHAS.md`.",
        ]
    )

    frontmatter_yaml = yaml.safe_dump(frontmatter, sort_keys=False).strip()
    body = "\n".join(body_lines).strip() + "\n"
    return f"---\n{frontmatter_yaml}\n---\n\n{body}"


def _slugify(name: str) -> str:
    value = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")
    value = re.sub(r"-{2,}", "-", value)
    return value[:64] or "generated-skill"


def _build_description(analysis: AnalyzerIR) -> str:
    triggers = []
    for workflow in analysis.workflows:
        triggers.append(workflow.name.lower())
        if len(triggers) >= 4:
            break

    if len(triggers) < 3:
        triggers.extend(["automate tasks", "call APIs", "run common workflows"])

    trigger_text = ", ".join(triggers[:4])
    return (
        f"Use {analysis.software} via the {analysis.interface} interface. "
        f"Use when asked to {trigger_text} for API workflows and task automation."
    )


def _extract_key_concepts(analysis: AnalyzerIR) -> list[str]:
    concepts = [f"Primary interface: {analysis.interface}"]
    concepts.extend(f"Capability group: {group.name}" for group in analysis.capability_groups[:3])
    if analysis.setup.env_vars:
        concepts.append(f"Environment variables: {', '.join(analysis.setup.env_vars)}")
    if len(concepts) < 3:
        concepts.append("Workflows should be executed in order to avoid state and validation issues")
    return concepts[:5]


def _render_workflow(workflow: Workflow) -> list[str]:
    lines = [f"### {workflow.name}", ""]
    for index, step in enumerate(workflow.steps, start=1):
        cleaned = re.sub(r"^\d+[.)]?\s*", "", step)
        lines.append(f"{index}. {cleaned}")
    warning = workflow.common_errors[0] if workflow.common_errors else "Validate inputs before running"
    lines.extend(["", f"Common mistake: {warning}", ""])
    return lines


def _ensure_workflow_count(
    workflows: list[Workflow], capability_groups: list
) -> list[Workflow]:
    output = list(workflows)
    if len(output) >= 3:
        return output

    for group in capability_groups:
        for capability in group.capabilities:
            output.append(
                Workflow(
                    name=f"Use {capability.name}",
                    steps=[
                        f"Import and initialize {group.name} dependencies",
                        f"Call {capability.function}",
                        "Validate and persist the response",
                    ],
                    common_errors=["Skipping validation of response fields"],
                )
            )
            if len(output) >= 3:
                return output

    while len(output) < 3:
        output.append(
            Workflow(
                name=f"Default workflow {len(output) + 1}",
                steps=[
                    "Prepare input payload",
                    "Execute interface call",
                    "Validate response",
                ],
                common_errors=["Missing required arguments"],
            )
        )
    return output


def _ensure_gotcha_count(gotchas: list[str]) -> list[str]:
    values = [entry for entry in gotchas if entry.strip()]
    if len(values) >= 5:
        return values

    for item in DEFAULT_GOTCHAS:
        if item not in values:
            values.append(item)
        if len(values) >= 5:
            break
    return values


def _build_quick_reference(analysis: AnalyzerIR) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for group in analysis.capability_groups:
        for capability in group.capabilities:
            rows.append((capability.name, capability.function))

    for workflow in analysis.workflows:
        if len(rows) >= 10:
            break
        rows.append((workflow.name, workflow.steps[0] if workflow.steps else "See workflow details"))

    while len(rows) < 10:
        rows.append((f"Operation {len(rows) + 1}", "See references/API_REFERENCE.md"))

    return rows[:10]
