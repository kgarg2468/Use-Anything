"""Helpers for merging generated SKILL content with an existing skill."""

from __future__ import annotations

import re
from dataclasses import dataclass

import yaml

CANONICAL_SECTIONS = {
    "## Setup",
    "## Key concepts",
    "## Core workflows",
    "## Important constraints",
    "## Quick reference",
    "## When to use references",
}


@dataclass(frozen=True)
class ParsedBody:
    preamble: list[str]
    sections: list[tuple[str, list[str]]]


def merge_skill_markdown(*, existing_skill: str, generated_skill: str) -> str:
    """Merge generated canonical sections into an existing SKILL markdown document."""

    existing_frontmatter, existing_body = _split_frontmatter(existing_skill)
    generated_frontmatter, generated_body = _split_frontmatter(generated_skill)

    merged_frontmatter = _merge_frontmatter(existing_frontmatter, generated_frontmatter)

    existing_parsed = _parse_body(existing_body)
    generated_parsed = _parse_body(generated_body)

    generated_headers = {header for header, _ in generated_parsed.sections}
    preserved_custom_sections = [
        (header, content)
        for header, content in existing_parsed.sections
        if header not in CANONICAL_SECTIONS and header not in generated_headers
    ]

    merged_sections = [*generated_parsed.sections, *preserved_custom_sections]
    merged_body = _render_body(
        preamble=generated_parsed.preamble,
        sections=merged_sections,
    )

    return _render_frontmatter(merged_frontmatter, merged_body)


def _split_frontmatter(markdown: str) -> tuple[dict, str]:
    match = re.match(r"^---\n(.*?)\n---\n?(.*)$", markdown, flags=re.DOTALL)
    if not match:
        return {}, markdown.strip()

    frontmatter = yaml.safe_load(match.group(1)) or {}
    if not isinstance(frontmatter, dict):
        frontmatter = {}
    return frontmatter, match.group(2).strip()


def _merge_frontmatter(existing_frontmatter: dict, generated_frontmatter: dict) -> dict:
    merged = dict(generated_frontmatter)

    existing_meta = existing_frontmatter.get("metadata", {})
    generated_meta = generated_frontmatter.get("metadata", {})

    if isinstance(existing_meta, dict):
        metadata = dict(existing_meta)
        if isinstance(generated_meta, dict):
            metadata.update(generated_meta)
        merged["metadata"] = metadata

    for key, value in existing_frontmatter.items():
        if key not in merged:
            merged[key] = value

    return merged


def _parse_body(body: str) -> ParsedBody:
    lines = body.splitlines()
    preamble: list[str] = []
    sections: list[tuple[str, list[str]]] = []

    current_header: str | None = None
    current_lines: list[str] = []

    for line in lines:
        if line.startswith("## "):
            if current_header is None:
                preamble = current_lines
            else:
                sections.append((current_header, current_lines))
            current_header = line
            current_lines = []
            continue
        current_lines.append(line)

    if current_header is None:
        preamble = current_lines
    else:
        sections.append((current_header, current_lines))

    return ParsedBody(preamble=preamble, sections=sections)


def _render_body(*, preamble: list[str], sections: list[tuple[str, list[str]]]) -> str:
    lines: list[str] = []
    lines.extend(preamble)

    if lines and lines[-1] != "":
        lines.append("")

    for header, content in sections:
        lines.append(header)
        lines.append("")
        lines.extend(content)
        if not content or content[-1] != "":
            lines.append("")

    return "\n".join(lines).strip() + "\n"


def _render_frontmatter(frontmatter: dict, body: str) -> str:
    if not frontmatter:
        return body
    frontmatter_yaml = yaml.safe_dump(frontmatter, sort_keys=False).strip()
    return f"---\n{frontmatter_yaml}\n---\n\n{body}"
