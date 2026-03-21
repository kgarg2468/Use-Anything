"""Audit summary reporting and risk-based merge blocking helpers."""

from __future__ import annotations

from use_anything.audit.taxonomy import AuditSummary, risk_level_for_category


def build_audit_summary(
    *,
    gate: str,
    status: str,
    duration_seconds: float,
    failure_category: str | None,
    module_coverage: dict[str, float],
) -> AuditSummary:
    normalized_status = "passed" if status.strip().lower() == "passed" else "failed"
    normalized_category = (failure_category or "").strip().lower() or None
    if normalized_status == "failed" and not normalized_category:
        normalized_category = "command_failed"

    risk_level = risk_level_for_category(normalized_category or "unknown")
    if normalized_status == "passed":
        risk_level = "low"

    return AuditSummary(
        gate=gate,
        status=normalized_status,
        duration_seconds=round(float(duration_seconds), 2),
        failure_category=normalized_category,  # type: ignore[arg-type]
        risk_level=risk_level,
        module_coverage=module_coverage,
    )


def should_block_merge(summary: AuditSummary) -> bool:
    return summary.requires_blocking()
