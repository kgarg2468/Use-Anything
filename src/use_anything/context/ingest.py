"""Context-document ingestion orchestrator."""

from __future__ import annotations

from pathlib import Path

from use_anything.context.budget import (
    DEFAULT_CONTEXT_DOC_MAX_TOKENS,
    DEFAULT_CONTEXT_DOC_TOTAL_MAX_TOKENS,
    apply_context_budget,
)
from use_anything.context.claims import extract_context_claims
from use_anything.context.code_signals import scan_supabase_code_signals
from use_anything.context.conflicts import detect_claim_conflicts
from use_anything.context.decisions import apply_warn_and_degrade
from use_anything.context.models import ContextIngestionResult
from use_anything.context.parser import parse_context_doc
from use_anything.context.staleness import evaluate_doc_freshness


def ingest_context_docs(
    *,
    doc_paths: list[Path | str],
    project_dir: Path | str | None = None,
    per_doc_max_tokens: int = DEFAULT_CONTEXT_DOC_MAX_TOKENS,
    total_max_tokens: int = DEFAULT_CONTEXT_DOC_TOTAL_MAX_TOKENS,
) -> ContextIngestionResult:
    docs: list[str] = []
    warnings: list[str] = []
    all_claims = []
    freshness_by_doc = {}

    for raw_path in doc_paths:
        path = Path(raw_path).expanduser().resolve()
        if not path.exists() or not path.is_file():
            warnings.append(f"{path}: context doc not found; skipping")
            continue
        parsed = parse_context_doc(path)
        docs.append(str(path))
        warnings.extend(parsed.warnings)

        freshness = evaluate_doc_freshness(parsed.doc)
        freshness_by_doc[str(path)] = freshness
        if freshness.warning:
            warnings.append(freshness.warning)

        all_claims.extend(extract_context_claims(parsed.doc))

    code_signals = []
    if project_dir:
        code_signals = scan_supabase_code_signals(project_dir)
    conflicts = detect_claim_conflicts(all_claims, code_signals)

    decision = apply_warn_and_degrade(
        all_claims,
        freshness_by_doc=freshness_by_doc,
        conflicts=conflicts,
    )
    warnings.extend(decision.warnings)

    budget = apply_context_budget(
        decision.accepted_claims,
        per_doc_max_tokens=per_doc_max_tokens,
        total_max_tokens=total_max_tokens,
    )
    if budget.truncated_claims:
        warnings.append(f"Truncated {budget.truncated_claims} context claims to fit token limits")
    if budget.dropped_claims:
        warnings.append(f"Dropped {budget.dropped_claims} context claims due to token budget limits")

    claims_dropped = len(decision.dropped_claims) + budget.dropped_claims
    return ContextIngestionResult(
        docs=docs,
        accepted_claims=budget.claims,
        code_signals=code_signals,
        warnings=_dedupe_preserve_order(warnings),
        conflicts=conflicts,
        claims_used=len(budget.claims),
        claims_dropped=claims_dropped,
        used_tokens=budget.used_tokens,
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
