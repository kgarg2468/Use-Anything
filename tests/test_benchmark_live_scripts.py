from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


def _write_suite(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "name": "live-suite",
                "agent": "codex",
                "optimization_goal": "accuracy-first",
                "configs": ["no-skill"],
                "targets": [
                    {
                        "id": "requests",
                        "target": "requests",
                        "tasks": [
                            {
                                "id": "task-1",
                                "prompt": "Run a basic request workflow",
                                "expected_output": "A successful workflow output",
                                "assertions": ["workflow", "output"],
                            }
                        ],
                    }
                ],
            }
        )
    )


def test_run_live_task_script_emits_json_and_artifact_in_fake_mode(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.json"
    _write_suite(suite_path)

    output_dir = tmp_path / "benchmark-1-run"
    output_dir.mkdir(parents=True, exist_ok=True)

    script_path = Path(__file__).resolve().parents[1] / "benchmark" / "scripts" / "run_live_task.py"
    env = dict(os.environ)
    env["USE_ANYTHING_BENCH_FAKE"] = "1"

    completed = subprocess.run(
        [
            "python3",
            str(script_path),
            "--suite",
            str(suite_path),
            "--target-id",
            "requests",
            "--task-id",
            "task-1",
            "--config",
            "no-skill",
            "--run-id",
            "test-run",
            "--workdir",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert "passed" in payload
    assert "total_tokens" in payload
    assert "duration_ms" in payload
    assert "skill_invoked" in payload

    artifact = output_dir / "live-runs" / "test-run__requests__task-1__no-skill.json"
    assert artifact.exists()


def test_verify_live_task_script_checks_artifact_and_env_context(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.json"
    _write_suite(suite_path)

    output_dir = tmp_path / "benchmark-1-run"
    live_dir = output_dir / "live-runs"
    live_dir.mkdir(parents=True, exist_ok=True)

    artifact = live_dir / "test-run__requests__task-1__no-skill.json"
    artifact.write_text(
        json.dumps(
            {
                "target_id": "requests",
                "task_id": "task-1",
                "config": "no-skill",
                "response": "workflow output with validation details",
            }
        )
    )

    script_path = Path(__file__).resolve().parents[1] / "benchmark" / "scripts" / "verify_live_task.py"
    env = dict(os.environ)
    env["USE_ANYTHING_BENCH_TARGET_ID"] = "requests"
    env["USE_ANYTHING_BENCH_TASK_ID"] = "task-1"
    env["USE_ANYTHING_BENCH_CONFIG"] = "no-skill"

    completed = subprocess.run(
        [
            "python3",
            str(script_path),
            "--suite",
            str(suite_path),
            "--output-dir",
            str(output_dir),
            "--run-id",
            "test-run",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert completed.returncode == 0
