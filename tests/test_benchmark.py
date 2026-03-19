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


def test_runner_preflight_fails_when_selected_config_is_missing(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.json"
    _write_suite(
        suite_path,
        {
            "name": "runner-preflight-missing-config",
            "targets": [
                {
                    "id": "requests",
                    "target": "requests",
                    "tasks": [
                        {
                            "id": "task-1",
                            "prompt": "Send a GET request",
                            "expected_output": "request works",
                            "commands": {
                                "no-skill": "python -c \"import json; print(json.dumps({'passed': True}))\"",
                            },
                            "verifier_command": "python -c \"import sys; sys.exit(0)\"",
                        }
                    ],
                }
            ],
        },
    )
    suite = load_benchmark_suite(suite_path)
    output_dir = tmp_path / "benchmark-preflight"

    result = BenchmarkRunner().run(
        suite=suite,
        output_dir=output_dir,
        configs=["no-skill", "generated-skill-default"],
        agent="codex",
    )

    summary = result["benchmark_summary"]
    assert summary["preflight"]["passed"] is False
    assert summary["completed_runs"] == 0
    assert summary["incomplete_reason_counts"]["missing_execution_config"] == 1


def test_runner_preflight_fails_when_verifier_missing_for_command_task(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.json"
    _write_suite(
        suite_path,
        {
            "name": "runner-preflight-missing-verifier",
            "targets": [
                {
                    "id": "requests",
                    "target": "requests",
                    "tasks": [
                        {
                            "id": "task-1",
                            "prompt": "Send a GET request",
                            "expected_output": "request works",
                            "commands": {
                                "no-skill": "python -c \"import json; print(json.dumps({'passed': True}))\"",
                            },
                        }
                    ],
                }
            ],
        },
    )
    suite = load_benchmark_suite(suite_path)
    output_dir = tmp_path / "benchmark-preflight-verifier"

    result = BenchmarkRunner().run(
        suite=suite,
        output_dir=output_dir,
        configs=["no-skill"],
        agent="codex",
    )

    summary = result["benchmark_summary"]
    assert summary["preflight"]["passed"] is False
    assert summary["incomplete_reason_counts"]["missing_verifier_command"] == 1


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


def test_runner_nonzero_command_cannot_report_passed_true(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.json"
    _write_suite(
        suite_path,
        {
            "name": "runner-nonzero-command",
            "targets": [
                {
                    "id": "requests",
                    "target": "requests",
                    "tasks": [
                        {
                            "id": "task-command-failed",
                            "prompt": "nonzero command should fail",
                            "expected_output": "done",
                            "commands": {
                                "no-skill": (
                                    "python -c \"import json,sys; "
                                    "print(json.dumps({'passed': True, 'total_tokens': 10, 'duration_ms': 5})); "
                                    "sys.exit(3)\""
                                )
                            },
                            "verifier_command": "python -c \"import sys; sys.exit(0)\"",
                        }
                    ],
                }
            ],
        },
    )
    suite = load_benchmark_suite(suite_path)
    output_dir = tmp_path / "benchmark-command-failed"

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
    assert record["error_type"] == "command_failed"


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


def test_runner_writes_required_benchmark_artifacts(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.json"
    _write_suite(
        suite_path,
        {
            "name": "runner-artifacts",
            "targets": [
                {
                    "id": "requests",
                    "target": "requests",
                    "tasks": [
                        {
                            "id": "artifact-task",
                            "prompt": "artifact task",
                            "expected_output": "done",
                            "replay_results": {
                                "no-skill": {"passed": False, "total_tokens": 100, "duration_ms": 1000},
                                "generated-skill-default": {"passed": True, "total_tokens": 180, "duration_ms": 1200},
                                "generated-skill-explicit": {"passed": True, "total_tokens": 190, "duration_ms": 1100},
                                "agents-md-doc-index": {"passed": True, "total_tokens": 160, "duration_ms": 1050},
                            },
                        }
                    ],
                }
            ],
        },
    )
    suite = load_benchmark_suite(suite_path)
    output_dir = tmp_path / "benchmark-artifacts"

    BenchmarkRunner().run(
        suite=suite,
        output_dir=output_dir,
        configs=list(DEFAULT_BENCHMARK_CONFIGS),
        agent="codex",
    )

    assert (output_dir / "raw_runs.jsonl").exists()
    assert (output_dir / "task_summary.json").exists()
    assert (output_dir / "benchmark_summary.json").exists()
    assert (output_dir / "benchmark_report.md").exists()


def test_comprehensive_suite_scaffold_meets_scale_requirement() -> None:
    suite_path = Path(__file__).resolve().parents[1] / "benchmark" / "comprehensive-codex-suite.json"
    suite = load_benchmark_suite(suite_path)

    assert len(suite.targets) >= 20
    assert all(len(target.tasks) >= 5 for target in suite.targets)


def test_comprehensive_suite_has_commands_and_verifier_for_all_configs() -> None:
    suite_path = Path(__file__).resolve().parents[1] / "benchmark" / "comprehensive-codex-suite.json"
    suite = load_benchmark_suite(suite_path)

    for target in suite.targets:
        for task in target.tasks:
            assert task.verifier_command
            for config in DEFAULT_BENCHMARK_CONFIGS:
                assert config in task.commands
                assert task.commands[config].strip()


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
                            "verifier_command": "python -c \"import sys; sys.exit(0)\"",
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
                            "verifier_command": "python -c \"import sys; sys.exit(0)\"",
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
                            "verifier_command": "python -c \"import sys; sys.exit(0)\"",
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


def test_runner_completes_all_four_configs_with_commands_and_verifier(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.json"
    _write_suite(
        suite_path,
        {
            "name": "runner-four-configs",
            "targets": [
                {
                    "id": "requests",
                    "target": "requests",
                    "tasks": [
                        {
                            "id": "task-1",
                            "prompt": "task",
                            "expected_output": "done",
                            "commands": {
                                "no-skill": "python -c \"import json; print(json.dumps({'passed': True}))\"",
                                "generated-skill-default": (
                                    "python -c \"import json; "
                                    "print(json.dumps({'passed': True, 'skill_invoked': True}))\""
                                ),
                                "generated-skill-explicit": (
                                    "python -c \"import json; "
                                    "print(json.dumps({'passed': True, 'skill_invoked': True}))\""
                                ),
                                "agents-md-doc-index": "python -c \"import json; print(json.dumps({'passed': True}))\"",
                            },
                            "verifier_command": "python -c \"import sys; sys.exit(0)\"",
                        }
                    ],
                }
            ],
        },
    )
    suite = load_benchmark_suite(suite_path)
    output_dir = tmp_path / "benchmark-four-configs"

    result = BenchmarkRunner().run(
        suite=suite,
        output_dir=output_dir,
        configs=list(DEFAULT_BENCHMARK_CONFIGS),
        agent="codex",
    )

    assert result["benchmark_summary"]["total_runs"] == 4
    assert result["benchmark_summary"]["completed_runs"] == 4
