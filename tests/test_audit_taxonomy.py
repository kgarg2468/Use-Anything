from __future__ import annotations

import subprocess

import httpx
import pytest
from jsonschema import ValidationError

from use_anything.audit.taxonomy import (
    FAILURE_CATEGORIES,
    AuditSummary,
    classify_failure_category,
    risk_level_for_category,
)


def test_failure_category_constants_cover_expected_contract() -> None:
    assert set(FAILURE_CATEGORIES) == {
        "timeout",
        "network",
        "auth",
        "rate_limit",
        "schema",
        "command_failed",
        "permission",
        "regression",
    }


def test_classify_failure_category_from_exception_types() -> None:
    request = httpx.Request("GET", "https://example.com")
    response_401 = httpx.Response(401, request=request)
    response_429 = httpx.Response(429, request=request)

    assert classify_failure_category(exc=subprocess.TimeoutExpired("cmd", timeout=1)) == "timeout"
    assert classify_failure_category(exc=httpx.ConnectError("boom", request=request)) == "network"
    assert (
        classify_failure_category(exc=httpx.HTTPStatusError("unauthorized", request=request, response=response_401))
        == "auth"
    )
    assert (
        classify_failure_category(exc=httpx.HTTPStatusError("limited", request=request, response=response_429))
        == "rate_limit"
    )
    assert classify_failure_category(exc=PermissionError("denied")) == "permission"
    assert classify_failure_category(exc=ValidationError("bad schema")) == "schema"


def test_classify_failure_category_uses_stderr_and_status_fallbacks() -> None:
    assert classify_failure_category(stderr="permission denied while writing file") == "permission"
    assert classify_failure_category(stderr="API returned 429 too many requests") == "rate_limit"
    assert classify_failure_category(stderr="authentication failed for API key") == "auth"
    assert classify_failure_category(stderr="socket timeout while connecting") == "timeout"
    assert classify_failure_category(stderr="plain command error", exit_code=1) == "command_failed"


def test_risk_level_for_category_mapping() -> None:
    assert risk_level_for_category("regression") == "critical"
    assert risk_level_for_category("schema") == "high"
    assert risk_level_for_category("auth") == "high"
    assert risk_level_for_category("rate_limit") == "high"
    assert risk_level_for_category("timeout") == "medium"
    assert risk_level_for_category("network") == "medium"
    assert risk_level_for_category("permission") == "medium"
    assert risk_level_for_category("command_failed") == "medium"
    assert risk_level_for_category("unknown") == "low"


def test_audit_summary_to_dict_emits_contract_fields() -> None:
    summary = AuditSummary(
        gate="test-fast",
        status="passed",
        duration_seconds=21.4,
        failure_category=None,
        risk_level="low",
        module_coverage={"pipeline": 92.3},
    )

    payload = summary.to_dict()
    assert payload["gate"] == "test-fast"
    assert payload["status"] == "passed"
    assert payload["duration_seconds"] == 21.4
    assert payload["failure_category"] is None
    assert payload["risk_level"] == "low"
    assert payload["module_coverage"] == {"pipeline": 92.3}


@pytest.mark.parametrize(
    ("status", "risk_level", "expected"),
    [
        ("failed", "critical", True),
        ("failed", "high", True),
        ("failed", "medium", False),
        ("passed", "critical", False),
    ],
)
def test_audit_summary_requires_blocking(status: str, risk_level: str, expected: bool) -> None:
    summary = AuditSummary(
        gate="test",
        status=status,
        duration_seconds=10.0,
        failure_category="regression" if status == "failed" else None,
        risk_level=risk_level,
        module_coverage={},
    )
    assert summary.requires_blocking() is expected
