"""Audit and test-hardening helpers."""

from use_anything.audit.coverage_gate import (
    CoverageGateResult,
    build_module_coverage,
    changed_modules_from_paths,
    evaluate_coverage_thresholds,
    overall_percent_from_payload,
)
from use_anything.audit.taxonomy import (
    FAILURE_CATEGORIES,
    RISK_LEVELS,
    AuditSummary,
    classify_failure_category,
    risk_level_for_category,
)

__all__ = [
    "FAILURE_CATEGORIES",
    "RISK_LEVELS",
    "AuditSummary",
    "classify_failure_category",
    "risk_level_for_category",
    "CoverageGateResult",
    "build_module_coverage",
    "changed_modules_from_paths",
    "evaluate_coverage_thresholds",
    "overall_percent_from_payload",
]
