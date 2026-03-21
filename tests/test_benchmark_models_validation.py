from __future__ import annotations

import json
from pathlib import Path

import pytest

from use_anything.benchmark.models import BenchmarkSuite, BenchmarkTarget, BenchmarkTask, load_benchmark_suite


def test_benchmark_task_rejects_invalid_replay_results_shapes() -> None:
    with pytest.raises(ValueError, match="replay_results must be an object"):
        BenchmarkTask.from_dict(
            {
                "id": "t1",
                "prompt": "p",
                "expected_output": "o",
                "replay_results": [],
            }
        )

    with pytest.raises(ValueError, match="replay_results keys must be non-empty strings"):
        BenchmarkTask.from_dict(
            {
                "id": "t1",
                "prompt": "p",
                "expected_output": "o",
                "replay_results": {1: {}},
            }
        )

    with pytest.raises(ValueError, match="must be an object"):
        BenchmarkTask.from_dict(
            {
                "id": "t1",
                "prompt": "p",
                "expected_output": "o",
                "replay_results": {"no-skill": "bad"},
            }
        )


def test_benchmark_task_rejects_invalid_optional_command_fields() -> None:
    with pytest.raises(ValueError, match="verifier_command must be a string"):
        BenchmarkTask.from_dict(
            {
                "id": "t1",
                "prompt": "p",
                "expected_output": "o",
                "verifier_command": 123,
            }
        )

    with pytest.raises(ValueError, match="workdir must be a string"):
        BenchmarkTask.from_dict(
            {
                "id": "t1",
                "prompt": "p",
                "expected_output": "o",
                "workdir": 123,
            }
        )


def test_benchmark_target_rejects_invalid_tasks() -> None:
    with pytest.raises(ValueError, match="tasks must be a non-empty list"):
        BenchmarkTarget.from_dict({"id": "x", "target": "requests", "tasks": []})

    with pytest.raises(ValueError, match="each task must be an object"):
        BenchmarkTarget.from_dict({"id": "x", "target": "requests", "tasks": ["bad"]})


def test_benchmark_suite_rejects_invalid_scalar_fields() -> None:
    base_target = {
        "id": "t",
        "target": "x",
        "tasks": [{"id": "a", "prompt": "p", "expected_output": "o"}],
    }

    with pytest.raises(ValueError, match="agent must be a non-empty string"):
        BenchmarkSuite.from_dict({"name": "suite", "agent": "", "targets": [base_target]})

    with pytest.raises(ValueError, match="optimization_goal must be a non-empty string"):
        BenchmarkSuite.from_dict({"name": "suite", "optimization_goal": "", "targets": [base_target]})


def test_benchmark_suite_rejects_invalid_configs_and_targets() -> None:
    with pytest.raises(ValueError, match="configs must include at least one config"):
        BenchmarkSuite.from_dict(
            {
                "name": "suite",
                "configs": [],
                "targets": [{"id": "t", "target": "x", "tasks": [{"id": "a", "prompt": "p", "expected_output": "o"}]}],
            }
        )

    with pytest.raises(ValueError, match="unknown config"):
        BenchmarkSuite.from_dict(
            {
                "name": "suite",
                "configs": ["no-skill", "not-real"],
                "targets": [{"id": "t", "target": "x", "tasks": [{"id": "a", "prompt": "p", "expected_output": "o"}]}],
            }
        )

    with pytest.raises(ValueError, match="targets must be a non-empty list"):
        BenchmarkSuite.from_dict({"name": "suite", "targets": []})

    with pytest.raises(ValueError, match="each target must be an object"):
        BenchmarkSuite.from_dict({"name": "suite", "targets": ["bad"]})

    with pytest.raises(ValueError, match="metadata must be an object"):
        BenchmarkSuite.from_dict(
            {
                "name": "suite",
                "targets": [{"id": "t", "target": "x", "tasks": [{"id": "a", "prompt": "p", "expected_output": "o"}]}],
                "metadata": "bad",
            }
        )


def test_load_benchmark_suite_rejects_file_and_json_errors(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    with pytest.raises(ValueError, match="suite file not found"):
        load_benchmark_suite(missing)

    invalid_json = tmp_path / "invalid.json"
    invalid_json.write_text("{bad", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid benchmark suite JSON"):
        load_benchmark_suite(invalid_json)

    not_object = tmp_path / "array.json"
    not_object.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    with pytest.raises(ValueError, match="suite root must be a JSON object"):
        load_benchmark_suite(not_object)
