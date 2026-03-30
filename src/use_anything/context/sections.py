"""Utilities for splitting and classifying markdown sections."""

from __future__ import annotations

import re

from use_anything.context.models import ContextSection

SECTION_HEADING_PATTERN = re.compile(r"^##+\s+(.*)$", flags=re.MULTILINE)
GENERIC_SECTION_MARKERS = (
    "overview",
    "introduction",
    "sdk",
    "api reference",
    "reference",
    "quickstart",
    "quick start",
    "getting started",
    "troubleshooting",
    "faq",
)


def split_markdown_sections(body: str) -> list[ContextSection]:
    matches = list(SECTION_HEADING_PATTERN.finditer(body))
    if not matches:
        content = body.strip()
        if not content:
            return []
        return [ContextSection(heading="(root)", body=content, generic=False)]

    sections: list[ContextSection] = []
    for idx, match in enumerate(matches):
        heading = match.group(1).strip()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
        segment = body[start:end].strip()
        if not segment:
            continue
        sections.append(
            ContextSection(
                heading=heading,
                body=segment,
                generic=is_generic_section(heading),
            )
        )
    return sections


def is_generic_section(heading: str) -> bool:
    normalized = " ".join(heading.lower().split())
    return any(marker in normalized for marker in GENERIC_SECTION_MARKERS)
