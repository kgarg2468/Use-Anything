"""Warn-and-degrade decisions for context claims."""

from __future__ import annotations

from use_anything.context.models import (
    ContextClaim,
    ContextClaimConflict,
    ContextDecisionResult,
    ContextDocFreshness,
)


def apply_warn_and_degrade(
    claims: list[ContextClaim],
    *,
    freshness_by_doc: dict[str, ContextDocFreshness],
    conflicts: list[ContextClaimConflict],
) -> ContextDecisionResult:
    conflict_keys = {(item.claim.text, item.claim.source_path) for item in conflicts}
    accepted_claims: list[ContextClaim] = []
    dropped_claims: list[ContextClaim] = []
    warnings: list[str] = []

    for claim in claims:
        freshness = freshness_by_doc.get(claim.source_path)
        key = (claim.text, claim.source_path)

        if freshness and freshness.stale:
            dropped_claims.append(claim)
            warnings.append(f"{claim.source_path}: dropped stale claim from section '{claim.source_section}'")
            continue

        if key in conflict_keys:
            dropped_claims.append(claim)
            warnings.append(f"{claim.source_path}: dropped claim conflicting with code signals")
            continue

        accepted_claims.append(claim)

    for conflict in conflicts:
        warnings.append(
            f"{conflict.claim.source_path}: conflict '{conflict.claim.text}' "
            f"vs {conflict.signal.kind} ({conflict.signal.path})"
        )

    return ContextDecisionResult(
        accepted_claims=accepted_claims,
        dropped_claims=dropped_claims,
        warnings=_dedupe_preserve_order(warnings),
        conflicts=conflicts,
    )


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output
