from __future__ import annotations

from use_anything.audit.reporting import build_audit_summary, should_block_merge


def test_build_audit_summary_uses_contract_fields() -> None:
    summary = build_audit_summary(
        gate="coverage-gate",
        status="passed",
        duration_seconds=12.3,
        failure_category=None,
        module_coverage={"pipeline": 93.4},
    )

    payload = summary.to_dict()
    assert payload["gate"] == "coverage-gate"
    assert payload["status"] == "passed"
    assert payload["duration_seconds"] == 12.3
    assert payload["failure_category"] is None
    assert payload["risk_level"] == "low"
    assert payload["module_coverage"] == {"pipeline": 93.4}


def test_build_audit_summary_defaults_failed_category_to_command_failed() -> None:
    summary = build_audit_summary(
        gate="test-live-smoke",
        status="failed",
        duration_seconds=20.0,
        failure_category=None,
        module_coverage={},
    )

    assert summary.failure_category == "command_failed"
    assert summary.risk_level == "medium"


def test_should_block_merge_for_high_or_critical_failed_risk() -> None:
    high = build_audit_summary(
        gate="schema-check",
        status="failed",
        duration_seconds=4.0,
        failure_category="schema",
        module_coverage={},
    )
    critical = build_audit_summary(
        gate="regression-check",
        status="failed",
        duration_seconds=4.0,
        failure_category="regression",
        module_coverage={},
    )
    medium = build_audit_summary(
        gate="smoke",
        status="failed",
        duration_seconds=4.0,
        failure_category="command_failed",
        module_coverage={},
    )

    assert should_block_merge(high) is True
    assert should_block_merge(critical) is True
    assert should_block_merge(medium) is False
