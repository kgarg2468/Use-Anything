from __future__ import annotations

from use_anything.audit.coverage_gate import (
    CoverageGateResult,
    build_module_coverage,
    changed_modules_from_paths,
    evaluate_coverage_thresholds,
    overall_percent_from_payload,
)


def _coverage_payload() -> dict:
    return {
        "totals": {"percent_covered": 93.4},
        "files": {
            "src/use_anything/pipeline.py": {"summary": {"percent_covered": 91.2}},
            "src/use_anything/analyze/providers.py": {"summary": {"percent_covered": 88.0}},
            "src/use_anything/__main__.py": {"summary": {"percent_covered": 72.5}},
        },
    }


def test_build_module_coverage_extracts_package_modules() -> None:
    module_coverage = build_module_coverage(_coverage_payload())

    assert module_coverage["pipeline"] == 91.2
    assert module_coverage["analyze/providers"] == 88.0
    assert module_coverage["__main__"] == 72.5


def test_evaluate_coverage_thresholds_passes_for_compliant_payload() -> None:
    result = evaluate_coverage_thresholds(
        overall_percent=93.4,
        module_coverage={
            "pipeline": 91.2,
            "analyze/providers": 88.0,
            "__main__": 72.5,
        },
        changed_modules=["pipeline", "analyze/providers"],
    )

    assert isinstance(result, CoverageGateResult)
    assert result.passed is True
    assert result.violations == []


def test_evaluate_coverage_thresholds_detects_overall_floor_violation() -> None:
    result = evaluate_coverage_thresholds(
        overall_percent=90.0,
        module_coverage={"pipeline": 92.0, "__main__": 75.0},
        changed_modules=[],
    )

    assert result.passed is False
    assert any("Overall coverage" in issue for issue in result.violations)


def test_evaluate_coverage_thresholds_detects_module_floors() -> None:
    result = evaluate_coverage_thresholds(
        overall_percent=93.0,
        module_coverage={
            "pipeline": 84.9,
            "analyze/providers": 60.0,
            "__main__": 69.9,
        },
        changed_modules=[],
    )

    assert result.passed is False
    assert any("pipeline" in issue for issue in result.violations)
    assert any("analyze/providers" in issue for issue in result.violations)
    assert any("__main__" in issue for issue in result.violations)


def test_evaluate_coverage_thresholds_detects_changed_module_regression() -> None:
    result = evaluate_coverage_thresholds(
        overall_percent=95.0,
        module_coverage={"pipeline": 92.0},
        changed_modules=["pipeline", "probe/pypi"],
    )

    assert result.passed is False
    assert any("probe/pypi" in issue for issue in result.violations)


def test_overall_percent_from_payload_defaults_to_zero_for_invalid_shape() -> None:
    assert overall_percent_from_payload({"totals": {"percent_covered": 88.5}}) == 88.5
    assert overall_percent_from_payload({"totals": {"percent_covered": "bad"}}) == 0.0
    assert overall_percent_from_payload({"totals": []}) == 0.0
    assert overall_percent_from_payload({}) == 0.0


def test_changed_modules_from_paths_normalizes_python_modules_only() -> None:
    modules = changed_modules_from_paths(
        [
            "src/use_anything/pipeline.py",
            "src/use_anything/probe/pypi.py",
            "src/use_anything/probe/__init__.py",
            "README.md",
            "src/use_anything/probe/pypi.py",
        ]
    )

    assert modules == ["pipeline", "probe", "probe/pypi"]


def test_coverage_gate_result_to_dict_serializes_all_fields() -> None:
    result = CoverageGateResult(
        passed=False,
        overall_percent=87.1,
        module_coverage={"pipeline": 80.0},
        violations=["low coverage"],
    )

    assert result.to_dict() == {
        "passed": False,
        "overall_percent": 87.1,
        "module_coverage": {"pipeline": 80.0},
        "violations": ["low coverage"],
    }


def test_build_module_coverage_ignores_invalid_entries() -> None:
    payload = {
        "files": {
            "src/use_anything/pipeline.py": {"summary": []},
            "src/use_anything/cli.py": {"summary": {"percent_covered": "bad"}},
            "src/use_anything/not-python.txt": {"summary": {"percent_covered": 90.0}},
            123: {"summary": {"percent_covered": 80.0}},
        }
    }

    module_coverage = build_module_coverage(payload)

    assert module_coverage == {"not-python.txt": 90.0}


def test_build_module_coverage_handles_non_dict_files_field() -> None:
    assert build_module_coverage({"files": []}) == {}


def test_private_module_name_helper_handles_non_python_suffix() -> None:
    import importlib

    module = importlib.import_module("use_anything.audit.coverage_gate")
    assert module._module_name_from_path(
        "src/use_anything/README.md",
        package_prefix="src/use_anything",
    ) == "README.md"
