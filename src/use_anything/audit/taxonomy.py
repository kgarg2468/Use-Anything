"""Shared audit failure taxonomy and gate summary helpers."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Literal

import httpx
from jsonschema import ValidationError

FailureCategory = Literal[
    "timeout",
    "network",
    "auth",
    "rate_limit",
    "schema",
    "command_failed",
    "permission",
    "regression",
]
RiskLevel = Literal["low", "medium", "high", "critical"]

FAILURE_CATEGORIES: tuple[FailureCategory, ...] = (
    "timeout",
    "network",
    "auth",
    "rate_limit",
    "schema",
    "command_failed",
    "permission",
    "regression",
)
RISK_LEVELS: tuple[RiskLevel, ...] = ("low", "medium", "high", "critical")


def classify_failure_category(
    *,
    exc: BaseException | None = None,
    stderr: str = "",
    exit_code: int | None = None,
) -> FailureCategory:
    """Classify command/provider failures into stable categories."""

    if isinstance(exc, subprocess.TimeoutExpired):
        return "timeout"
    if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        return "timeout"
    if isinstance(exc, httpx.ConnectError | httpx.NetworkError):
        return "network"
    if isinstance(exc, PermissionError):
        return "permission"
    if isinstance(exc, ValidationError):
        return "schema"
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        if status_code in {401, 403}:
            return "auth"
        if status_code == 429:
            return "rate_limit"
        if status_code >= 500:
            return "network"

    text = (stderr or "").lower()
    if "permission denied" in text or "operation not permitted" in text:
        return "permission"
    if "429" in text or "rate limit" in text or "too many requests" in text:
        return "rate_limit"
    if "unauthorized" in text or "authentication failed" in text or "invalid token" in text:
        return "auth"
    if "timeout" in text:
        return "timeout"
    if "schema" in text or "validationerror" in text:
        return "schema"

    if exit_code and exit_code != 0:
        return "command_failed"
    return "command_failed"


def risk_level_for_category(category: str) -> RiskLevel:
    """Map failure categories to risk levels for merge-blocking decisions."""

    if category == "regression":
        return "critical"
    if category in {"schema", "auth", "rate_limit"}:
        return "high"
    if category in {"timeout", "network", "permission", "command_failed"}:
        return "medium"
    return "low"


@dataclass(frozen=True)
class AuditSummary:
    gate: str
    status: str
    duration_seconds: float
    failure_category: FailureCategory | None
    risk_level: RiskLevel
    module_coverage: dict[str, float]

    def to_dict(self) -> dict[str, object]:
        return {
            "gate": self.gate,
            "status": self.status,
            "duration_seconds": self.duration_seconds,
            "failure_category": self.failure_category,
            "risk_level": self.risk_level,
            "module_coverage": self.module_coverage,
        }

    def requires_blocking(self) -> bool:
        return self.status == "failed" and self.risk_level in {"critical", "high"}
