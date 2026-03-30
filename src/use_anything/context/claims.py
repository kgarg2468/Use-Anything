"""Extract concise context claims from parsed markdown docs."""

from __future__ import annotations

import re

from use_anything.context.models import ContextClaim, ContextDoc, ContextSection
from use_anything.context.sections import split_markdown_sections

MIN_CLAIM_CHARS = 15
MAX_CLAIM_CHARS = 280


def extract_context_claims(doc: ContextDoc) -> list[ContextClaim]:
    sections = split_markdown_sections(doc.body)
    if not sections:
        return []

    claims: list[ContextClaim] = []
    for section in sections:
        if section.generic:
            continue
        claims.extend(_claims_from_section(doc, section))

    return _dedupe_claims(claims)


def _claims_from_section(doc: ContextDoc, section: ContextSection) -> list[ContextClaim]:
    claims: list[ContextClaim] = []
    lines = [line.strip() for line in section.body.splitlines() if line.strip()]

    for line in lines:
        cleaned = re.sub(r"^[-*]\s+", "", line)
        cleaned = re.sub(r"^\d+\.\s+", "", cleaned)
        if _looks_like_claim(cleaned):
            claims.append(
                ContextClaim(
                    text=cleaned,
                    source_path=str(doc.path),
                    source_section=section.heading,
                )
            )

    if claims:
        return claims

    collapsed = " ".join(lines)
    for sentence in re.split(r"(?<=[.!?])\s+", collapsed):
        if _looks_like_claim(sentence):
            claims.append(
                ContextClaim(
                    text=sentence.strip(),
                    source_path=str(doc.path),
                    source_section=section.heading,
                )
            )
    return claims


def _looks_like_claim(value: str) -> bool:
    text = " ".join(value.split())
    if len(text) < MIN_CLAIM_CHARS:
        return False
    if len(text) > MAX_CLAIM_CHARS:
        return False
    alpha_chars = sum(1 for char in text if char.isalpha())
    return alpha_chars >= 8


def _dedupe_claims(claims: list[ContextClaim]) -> list[ContextClaim]:
    seen: set[str] = set()
    output: list[ContextClaim] = []
    for claim in claims:
        key = " ".join(claim.text.lower().split())
        if key in seen:
            continue
        seen.add(key)
        output.append(claim)
    return output
