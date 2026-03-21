"""Coverage floor and changed-module gate helpers for audit workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

OVERALL_COVERAGE_FLOOR = 92.0
MODULE_COVERAGE_FLOOR = 85.0
MAIN_MODULE_COVERAGE_FLOOR = 70.0


@dataclass(frozen=True)
class CoverageGateResult:
    passed: bool
    overall_percent: float
    module_coverage: dict[str, float]
    violations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "overall_percent": self.overall_percent,
            "module_coverage": self.module_coverage,
            "violations": self.violations,
        }


def build_module_coverage(
    coverage_payload: dict[str, Any],
    *,
    package_prefix: str = "src/use_anything",
) -> dict[str, float]:
    """Convert coverage.py JSON payload file stats into module keyed percentages."""

    files = coverage_payload.get("files", {})
    if not isinstance(files, dict):
        return {}

    module_coverage: dict[str, float] = {}
    normalized_prefix = package_prefix.strip("/").replace("\\", "/")

    for raw_path, payload in files.items():
        if not isinstance(raw_path, str) or not isinstance(payload, dict):
            continue
        normalized = raw_path.replace("\\", "/")
        if not normalized.startswith(normalized_prefix + "/"):
            continue

        summary = payload.get("summary", {})
        if not isinstance(summary, dict):
            continue
        percent = summary.get("percent_covered")
        if not isinstance(percent, int | float):
            continue

        module_name = _module_name_from_path(normalized, package_prefix=normalized_prefix)
        module_coverage[module_name] = round(float(percent), 2)

    return module_coverage


def evaluate_coverage_thresholds(
    *,
    overall_percent: float,
    module_coverage: dict[str, float],
    changed_modules: list[str],
    overall_floor: float = OVERALL_COVERAGE_FLOOR,
    module_floor: float = MODULE_COVERAGE_FLOOR,
    main_floor: float = MAIN_MODULE_COVERAGE_FLOOR,
) -> CoverageGateResult:
    """Evaluate overall, per-module, and changed-module coverage requirements."""

    violations: list[str] = []

    if overall_percent < overall_floor:
        violations.append(f"Overall coverage {overall_percent:.2f}% is below required {overall_floor:.2f}%")

    for module_name, percent in sorted(module_coverage.items()):
        required = main_floor if module_name == "__main__" else module_floor
        if percent < required:
            violations.append(f"Module '{module_name}' coverage {percent:.2f}% is below required {required:.2f}%")

    for module_name in sorted(set(changed_modules)):
        if module_name and module_name not in module_coverage:
            violations.append(f"Changed module '{module_name}' is missing from coverage report")

    return CoverageGateResult(
        passed=not violations,
        overall_percent=round(float(overall_percent), 2),
        module_coverage=dict(sorted(module_coverage.items())),
        violations=violations,
    )


def overall_percent_from_payload(coverage_payload: dict[str, Any]) -> float:
    totals = coverage_payload.get("totals", {})
    if not isinstance(totals, dict):
        return 0.0
    percent = totals.get("percent_covered", 0.0)
    if not isinstance(percent, int | float):
        return 0.0
    return float(percent)


def changed_modules_from_paths(paths: list[str], *, package_prefix: str = "src/use_anything") -> list[str]:
    modules: list[str] = []
    normalized_prefix = package_prefix.strip("/").replace("\\", "/")

    for path in paths:
        normalized = path.replace("\\", "/")
        if not normalized.startswith(normalized_prefix + "/"):
            continue
        if not normalized.endswith(".py"):
            continue
        module_name = _module_name_from_path(normalized, package_prefix=normalized_prefix)
        modules.append(module_name)
    return sorted(set(modules))


def _module_name_from_path(raw_path: str, *, package_prefix: str) -> str:
    relative = raw_path[len(package_prefix) + 1 :]
    posix = PurePosixPath(relative)
    if posix.name == "__init__.py":
        parent = str(posix.parent)
        return parent if parent not in {".", ""} else "__init__"
    if posix.suffix == ".py":
        return str(posix.with_suffix(""))
    return str(Path(relative))
