from __future__ import annotations

import json
from pathlib import Path

import pytest

from use_anything.benchmark.models import load_benchmark_suite
from use_anything.benchmark.runner import BenchmarkRunner


def _write_suite(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


@pytest.mark.benchmark
def test_benchmark_suite_rejects_unknown_config(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.json"
    _write_suite(
        suite_path,
        {
            "name": "unknown-config-suite",
            "configs": ["no-skill", "unsupported-config"],
            "targets": [
                {
                    "id": "requests",
                    "target": "requests",
                    "tasks": [{"id": "task-1", "prompt": "x", "expected_output": "y"}],
                }
            ],
        },
    )

    with pytest.raises(ValueError, match="unknown config"):
        load_benchmark_suite(suite_path)


@pytest.mark.benchmark
def test_runner_timeout_seconds_falls_back_to_default_on_invalid_env(monkeypatch) -> None:
    runner = BenchmarkRunner()
    monkeypatch.setenv(runner.TASK_TIMEOUT_ENV, "not-a-number")

    timeout = runner._timeout_seconds(override=None, env_name=runner.TASK_TIMEOUT_ENV, default=123)

    assert timeout == 123


@pytest.mark.benchmark
def test_runner_extract_payload_ignores_non_object_json() -> None:
    runner = BenchmarkRunner()

    assert runner._extract_payload('["not", "an", "object"]') == {}
    assert runner._extract_payload("not-json") == {}
    assert runner._extract_payload("") == {}


@pytest.mark.benchmark
def test_runner_merge_reason_counts_accumulates_overlap() -> None:
    runner = BenchmarkRunner()

    merged = runner._merge_reason_counts(
        {"missing_execution_config": 2, "verification_failed": 1},
        {"missing_execution_config": 3, "command_timeout": 1},
    )

    assert merged == {
        "missing_execution_config": 5,
        "verification_failed": 1,
        "command_timeout": 1,
    }


@pytest.mark.benchmark
def test_runner_report_includes_none_when_no_incomplete_reasons() -> None:
    runner = BenchmarkRunner()
    report = runner._render_report_markdown(
        suite_name="demo",
        benchmark_summary={
            "suite": "demo",
            "total_runs": 1,
            "completed_runs": 1,
            "completion_rate": 1.0,
            "preflight": {"passed": True},
            "incomplete_reason_counts": {},
            "config_stats": {
                "no-skill": {
                    "pass_rate": 1.0,
                    "tokens_mean": 10.0,
                    "duration_ms_mean": 5.0,
                    "skill_invocation_rate": 0.0,
                }
            },
            "delta_vs_no_skill": {},
        },
    )

    assert "## Incomplete Reason Counts" in report
    assert "- none" in report
