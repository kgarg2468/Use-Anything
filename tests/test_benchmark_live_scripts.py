from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from pathlib import Path


def _write_suite(path: Path, *, required_evidence: list[str] | None = None) -> None:
    task_payload: dict[str, object] = {
        "id": "task-1",
        "prompt": "Run a basic request workflow",
        "expected_output": "A successful workflow output",
        "assertions": ["workflow", "output"],
    }
    if required_evidence is not None:
        task_payload["required_evidence"] = required_evidence

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
                        "tasks": [task_payload],
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


def test_verify_live_task_script_enforces_required_evidence(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.json"
    _write_suite(suite_path, required_evidence=["requests", "workflow"])

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

    assert completed.returncode == 1

    artifact.write_text(
        json.dumps(
            {
                "target_id": "requests",
                "task_id": "task-1",
                "config": "no-skill",
                "response": "requests workflow output with validation details",
            }
        )
    )
    completed_ok = subprocess.run(
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
    assert completed_ok.returncode == 0


def test_run_live_task_codex_timeout_maps_to_codex_exec_timeout(tmp_path: Path, monkeypatch) -> None:
    script_path = Path(__file__).resolve().parents[1] / "benchmark" / "scripts" / "run_live_task.py"
    spec = importlib.util.spec_from_file_location("run_live_task_module", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    monkeypatch.setattr(module.shutil, "which", lambda _: "/usr/bin/codex")

    def fake_run(*args, **kwargs):  # noqa: ANN002, ANN003
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=1)

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    returncode, response, error_type = module._execute_codex("prompt", tmp_path, timeout_seconds=1)

    assert returncode == 124
    assert response == ""
    assert error_type == "codex_exec_timeout"
