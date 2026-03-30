"""Parser for markdown context documents with optional frontmatter."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from use_anything.context.models import ContextDoc, ContextDocFrontmatter, ContextDocParseResult

FRONTMATTER_PATTERN = re.compile(r"^---\n(.*?)\n---\n?(.*)$", flags=re.DOTALL)


def parse_context_doc(path: Path | str) -> ContextDocParseResult:
    target = Path(path)
    raw_text = target.read_text(encoding="utf-8")

    frontmatter_text, body = _split_frontmatter(raw_text)
    frontmatter, warnings = _parse_frontmatter(frontmatter_text, source=str(target))

    return ContextDocParseResult(
        doc=ContextDoc(
            path=target,
            raw_text=raw_text,
            body=body,
            frontmatter=frontmatter,
        ),
        warnings=warnings,
    )


def _split_frontmatter(raw_text: str) -> tuple[str | None, str]:
    match = FRONTMATTER_PATTERN.match(raw_text)
    if not match:
        return None, raw_text
    return match.group(1), match.group(2)


def _parse_frontmatter(raw: str | None, *, source: str) -> tuple[ContextDocFrontmatter, list[str]]:
    if raw is None:
        return ContextDocFrontmatter(), []

    warnings: list[str] = []
    parsed: dict[str, Any]
    try:
        loaded = yaml.safe_load(raw) or {}
    except yaml.YAMLError as exc:
        warnings.append(f"{source}: invalid frontmatter YAML ({exc})")
        return ContextDocFrontmatter(), warnings

    if not isinstance(loaded, dict):
        warnings.append(f"{source}: frontmatter must be a YAML object")
        return ContextDocFrontmatter(), warnings
    parsed = loaded

    verified = _parse_iso_date(parsed.get("last_verified"), source=source, warnings=warnings)
    scope = str(parsed.get("scope", "")).strip().lower()
    owner = str(parsed.get("owner", "")).strip()
    applies_to = _normalize_applies_to(parsed.get("applies_to"), source=source, warnings=warnings)

    return (
        ContextDocFrontmatter(
            last_verified=verified,
            scope=scope,
            owner=owner,
            applies_to=applies_to,
            raw=parsed,
        ),
        warnings,
    )


def _parse_iso_date(value: Any, *, source: str, warnings: list[str]) -> date | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        warnings.append(f"{source}: last_verified must be ISO date (YYYY-MM-DD)")
        return None


def _normalize_applies_to(value: Any, *, source: str, warnings: list[str]) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        normalized = value.strip()
        return [normalized] if normalized else []
    if isinstance(value, list):
        output: list[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                output.append(text)
        return output

    warnings.append(f"{source}: applies_to should be a string or list of strings")
    return []
