from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _suite_with_replay(path: Path, *, missing_config: bool) -> None:
    task = {
        "id": "task-1",
        "prompt": "task prompt",
        "expected_output": "done",
        "replay_results": {
            "no-skill": {"passed": True, "total_tokens": 10, "duration_ms": 10},
            "generated-skill-default": {"passed": True, "total_tokens": 10, "duration_ms": 10},
            "generated-skill-explicit": {"passed": True, "total_tokens": 10, "duration_ms": 10},
            "agents-md-doc-index": {"passed": True, "total_tokens": 10, "duration_ms": 10},
        },
    }
    if missing_config:
        task["replay_results"].pop("agents-md-doc-index")

    payload = {
        "name": "rerun-test-suite",
        "agent": "codex",
        "optimization_goal": "accuracy-first",
        "configs": [
            "no-skill",
            "generated-skill-default",
            "generated-skill-explicit",
            "agents-md-doc-index",
        ],
        "targets": [
            {"id": "t1", "target": "requests", "tasks": [task]},
            {"id": "t2", "target": "flask", "tasks": [task]},
        ],
    }
    path.write_text(json.dumps(payload, indent=2))


def test_rerun_script_archives_existing_outputs_and_runs_pilot(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.json"
    _suite_with_replay(suite_path, missing_config=False)

    output_dir = tmp_path / "benchmark-1-run"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "raw_runs.jsonl").write_text("old")

    script_path = Path(__file__).resolve().parents[1] / "benchmark" / "scripts" / "rerun_benchmark1.py"
    completed = subprocess.run(
        [
            "python3",
            str(script_path),
            "--suite",
            str(suite_path),
            "--output-dir",
            str(output_dir),
            "--pilot-targets",
            "1",
            "--skip-full-run",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert (output_dir / "benchmark_summary.json").exists()
    archives = list((output_dir / "archive").glob("*"))
    assert archives


def test_rerun_script_fails_when_pilot_gate_not_met(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.json"
    _suite_with_replay(suite_path, missing_config=True)

    output_dir = tmp_path / "benchmark-1-run"
    output_dir.mkdir(parents=True, exist_ok=True)

    script_path = Path(__file__).resolve().parents[1] / "benchmark" / "scripts" / "rerun_benchmark1.py"
    completed = subprocess.run(
        [
            "python3",
            str(script_path),
            "--suite",
            str(suite_path),
            "--output-dir",
            str(output_dir),
            "--pilot-targets",
            "1",
            "--skip-full-run",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 1
