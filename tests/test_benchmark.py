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
