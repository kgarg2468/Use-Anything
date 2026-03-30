"""Typed models for context-document processing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ContextDocFrontmatter:
    last_verified: date | None = None
    scope: str = ""
    owner: str = ""
    applies_to: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ContextDoc:
    path: Path
    raw_text: str
    body: str
    frontmatter: ContextDocFrontmatter


@dataclass(frozen=True)
class ContextClaim:
    text: str
    source_path: str
    source_section: str


@dataclass(frozen=True)
class ContextCodeSignal:
    kind: str
    value: str
    path: str


@dataclass(frozen=True)
class ContextClaimConflict:
    claim: ContextClaim
    signal: ContextCodeSignal
    reason: str


@dataclass(frozen=True)
class ContextDecision:
    claim: ContextClaim
    accepted: bool
    reason: str


@dataclass(frozen=True)
class ContextDocParseResult:
    doc: ContextDoc
    warnings: list[str]


@dataclass(frozen=True)
class ContextDocFreshness:
    stale: bool
    age_days: int | None
    warning: str | None = None


@dataclass(frozen=True)
class ContextSection:
    heading: str
    body: str
    generic: bool


@dataclass(frozen=True)
class ContextBudgetResult:
    claims: list[ContextClaim]
    used_tokens: int
    dropped_claims: int
    truncated_claims: int
