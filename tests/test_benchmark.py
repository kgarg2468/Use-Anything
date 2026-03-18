from __future__ import annotations

import json
from pathlib import Path

import pytest

from use_anything.benchmark.models import (
    DEFAULT_BENCHMARK_CONFIGS,
    BenchmarkSuite,
    load_benchmark_suite,
)
from use_anything.benchmark.runner import BenchmarkRunner


def _write_suite(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2))


def test_load_benchmark_suite_rejects_missing_required_fields(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.json"
    _write_suite(suite_path, {"name": "demo"})

    with pytest.raises(ValueError, match="targets"):
        load_benchmark_suite(suite_path)


def test_load_benchmark_suite_parses_valid_payload(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.json"
    _write_suite(
        suite_path,
        {
            "name": "comprehensive-codex",
            "agent": "codex",
            "optimization_goal": "accuracy-first",
            "targets": [
                {
                    "id": "requests",
                    "target": "requests",
                    "tasks": [
                        {
                            "id": "basic-get",
                            "prompt": "Send an HTTP GET request to example.com",
                            "expected_output": "A successful GET example",
                        }
                    ],
                }
            ],
        },
    )

    suite = load_benchmark_suite(suite_path)

    assert isinstance(suite, BenchmarkSuite)
    assert suite.agent == "codex"
    assert suite.optimization_goal == "accuracy-first"
    assert suite.targets[0].tasks[0].id == "basic-get"


def test_load_benchmark_suite_defaults_configs(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.json"
    _write_suite(
        suite_path,
        {
            "name": "defaults",
            "targets": [
                {
                    "id": "t1",
                    "target": "requests",
                    "tasks": [
                        {
                            "id": "task-1",
                            "prompt": "x",
                            "expected_output": "y",
                        }
                    ],
                }
            ],
        },
    )

    suite = load_benchmark_suite(suite_path)

    assert suite.configs == DEFAULT_BENCHMARK_CONFIGS


def test_runner_executes_no_skill_from_replay_results(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.json"
    _write_suite(
        suite_path,
        {
            "name": "runner-demo",
            "targets": [
                {
                    "id": "requests",
                    "target": "requests",
                    "tasks": [
                        {
                            "id": "task-1",
                            "prompt": "Send a GET request",
                            "expected_output": "request works",
                            "replay_results": {
                                "no-skill": {
                                    "passed": True,
                                    "total_tokens": 1234,
                                    "duration_ms": 2500,
                                    "skill_invoked": False,
                                }
                            },
                        }
                    ],
                }
            ],
        },
    )
    suite = load_benchmark_suite(suite_path)
    output_dir = tmp_path / "benchmark-1-run"

    result = BenchmarkRunner().run(
        suite=suite,
        output_dir=output_dir,
        configs=["no-skill"],
        agent="codex",
    )

    assert result["benchmark_summary"]["total_runs"] == 1
    assert result["benchmark_summary"]["completed_runs"] == 1


def test_runner_applies_verifier_command_and_marks_failure(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.json"
    _write_suite(
        suite_path,
        {
            "name": "runner-demo-verifier",
            "targets": [
                {
                    "id": "requests",
                    "target": "requests",
                    "tasks": [
                        {
                            "id": "task-verifier",
                            "prompt": "run with verifier",
                            "expected_output": "done",
                            "commands": {
                                "no-skill": (
                                    "python -c \"import json; "
                                    "print(json.dumps({'passed': True, 'total_tokens': 333, 'duration_ms': 1200}))\""
                                )
                            },
                            "verifier_command": "python -c \"import sys; sys.exit(1)\"",
                        }
                    ],
                }
            ],
        },
    )
    suite = load_benchmark_suite(suite_path)
    output_dir = tmp_path / "benchmark-verifier"

    BenchmarkRunner().run(
        suite=suite,
        output_dir=output_dir,
        configs=["no-skill"],
        agent="codex",
    )

    raw_runs = (output_dir / "raw_runs.jsonl").read_text().strip().splitlines()
    assert len(raw_runs) == 1
    record = json.loads(raw_runs[0])
    assert record["passed"] is False
    assert record["error_type"] == "verification_failed"
    assert record["total_tokens"] == 333


def test_runner_aggregates_config_stats_and_deltas(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.json"
    _write_suite(
        suite_path,
        {
            "name": "runner-summary",
            "targets": [
                {
                    "id": "requests",
                    "target": "requests",
                    "tasks": [
                        {
                            "id": "task-summary",
                            "prompt": "summary task",
                            "expected_output": "done",
                            "replay_results": {
                                "no-skill": {
                                    "passed": False,
                                    "total_tokens": 100,
                                    "duration_ms": 1000,
                                    "skill_invoked": False,
                                },
                                "generated-skill-default": {
                                    "passed": True,
                                    "total_tokens": 200,
                                    "duration_ms": 1500,
                                    "skill_invoked": True,
                                },
                                "generated-skill-explicit": {
                                    "passed": True,
                                    "total_tokens": 250,
                                    "duration_ms": 1600,
                                    "skill_invoked": True,
                                },
                                "agents-md-doc-index": {
                                    "passed": True,
                                    "total_tokens": 180,
                                    "duration_ms": 1200,
                                    "skill_invoked": False,
                                },
                            },
                        }
                    ],
                }
            ],
        },
    )
    suite = load_benchmark_suite(suite_path)
    output_dir = tmp_path / "benchmark-summary"

    result = BenchmarkRunner().run(
        suite=suite,
        output_dir=output_dir,
        configs=list(DEFAULT_BENCHMARK_CONFIGS),
        agent="codex",
    )

    summary = result["benchmark_summary"]
    assert summary["config_stats"]["no-skill"]["pass_rate"] == 0.0
    assert summary["config_stats"]["generated-skill-default"]["pass_rate"] == 1.0
    assert summary["delta_vs_no_skill"]["generated-skill-default"]["pass_rate_delta"] == 1.0
    assert summary["delta_vs_no_skill"]["generated-skill-default"]["tokens_delta"] == 100.0
    assert (output_dir / "raw_runs.jsonl").exists()


def test_runner_executes_generated_skill_default_from_command(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.json"
    _write_suite(
        suite_path,
        {
            "name": "runner-demo-default",
            "targets": [
                {
                    "id": "requests",
                    "target": "requests",
                    "tasks": [
                        {
                            "id": "task-default",
                            "prompt": "Use generated skill defaults",
                            "expected_output": "done",
                            "commands": {
                                "generated-skill-default": (
                                    "python -c \"import json; "
                                    "print(json.dumps({'passed': True, 'total_tokens': 200, "
                                    "'duration_ms': 900, 'skill_invoked': True}))\""
                                )
                            },
                        }
                    ],
                }
            ],
        },
    )
    suite = load_benchmark_suite(suite_path)
    output_dir = tmp_path / "benchmark-default"

    result = BenchmarkRunner().run(
        suite=suite,
        output_dir=output_dir,
        configs=["generated-skill-default"],
        agent="codex",
    )

    assert result["benchmark_summary"]["total_runs"] == 1
    assert result["benchmark_summary"]["completed_runs"] == 1


def test_runner_executes_generated_skill_explicit_from_command(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.json"
    _write_suite(
        suite_path,
        {
            "name": "runner-demo-explicit",
            "targets": [
                {
                    "id": "requests",
                    "target": "requests",
                    "tasks": [
                        {
                            "id": "task-explicit",
                            "prompt": "Use generated skill explicitly",
                            "expected_output": "done",
                            "commands": {
                                "generated-skill-explicit": (
                                    "python -c \"import json; "
                                    "print(json.dumps({'passed': True, 'total_tokens': 220, 'duration_ms': 800}))\""
                                )
                            },
                        }
                    ],
                }
            ],
        },
    )
    suite = load_benchmark_suite(suite_path)
    output_dir = tmp_path / "benchmark-explicit"

    result = BenchmarkRunner().run(
        suite=suite,
        output_dir=output_dir,
        configs=["generated-skill-explicit"],
        agent="codex",
    )

    assert result["benchmark_summary"]["total_runs"] == 1
    assert result["benchmark_summary"]["completed_runs"] == 1


def test_runner_executes_agents_md_baseline_from_command(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.json"
    _write_suite(
        suite_path,
        {
            "name": "runner-demo-agents",
            "targets": [
                {
                    "id": "requests",
                    "target": "requests",
                    "tasks": [
                        {
                            "id": "task-agents",
                            "prompt": "Use AGENTS.md docs baseline",
                            "expected_output": "done",
                            "commands": {
                                "agents-md-doc-index": (
                                    "python -c \"import json; "
                                    "print(json.dumps({'passed': True, 'total_tokens': 180, 'duration_ms': 700}))\""
                                )
                            },
                        }
                    ],
                }
            ],
        },
    )
    suite = load_benchmark_suite(suite_path)
    output_dir = tmp_path / "benchmark-agents"

    result = BenchmarkRunner().run(
        suite=suite,
        output_dir=output_dir,
        configs=["agents-md-doc-index"],
        agent="codex",
    )

    assert result["benchmark_summary"]["total_runs"] == 1
    assert result["benchmark_summary"]["completed_runs"] == 1
