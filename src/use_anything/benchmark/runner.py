"""Benchmark runner orchestration."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from use_anything.benchmark.models import BenchmarkSuite, BenchmarkTarget, BenchmarkTask


class BenchmarkRunner:
    """Run benchmark suites and return structured summaries."""

    def run(
        self,
        *,
        suite: BenchmarkSuite,
        output_dir: Path,
        configs: list[str],
        agent: str,
    ) -> dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)

        records: list[dict[str, Any]] = []
        for target in suite.targets:
            for task in target.tasks:
                for config in configs:
                    records.append(self._execute_task(target=target, task=task, config=config))

        raw_path = output_dir / "raw_runs.jsonl"
        raw_path.write_text("".join(json.dumps(record, sort_keys=True) + "\n" for record in records))

        completed_runs = sum(1 for record in records if record["status"] == "completed")
        return {
            "benchmark_summary": {
                "suite": suite.name,
                "agent": agent,
                "configs": configs,
                "total_runs": len(records),
                "completed_runs": completed_runs,
            },
            "output_dir": str(output_dir),
        }

    def _execute_task(self, *, target: BenchmarkTarget, task: BenchmarkTask, config: str) -> dict[str, Any]:
        payload = task.replay_results.get(config)
        if payload is not None:
            return {
                "target_id": target.id,
                "target": target.target,
                "task_id": task.id,
                "config": config,
                "passed": bool(payload.get("passed", False)),
                "total_tokens": int(payload.get("total_tokens", 0)),
                "duration_ms": int(payload.get("duration_ms", 0)),
                "skill_invoked": bool(payload.get("skill_invoked", False)),
                "error_type": payload.get("error_type"),
                "status": "completed",
            }

        command = task.commands.get(config)
        if command:
            start = time.perf_counter()
            completed = subprocess.run(
                command,
                shell=True,
                cwd=task.workdir or None,
                capture_output=True,
                text=True,
                check=False,
            )
            command_payload = self._extract_payload(completed.stdout)
            passed = bool(command_payload.get("passed", completed.returncode == 0))
            error_type = command_payload.get("error_type")

            if task.verifier_command:
                verifier = subprocess.run(
                    task.verifier_command,
                    shell=True,
                    cwd=task.workdir or None,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if verifier.returncode != 0:
                    passed = False
                    error_type = "verification_failed"

            elapsed_ms = int((time.perf_counter() - start) * 1000)
            if completed.returncode != 0 and not error_type:
                error_type = "command_failed"

            return {
                "target_id": target.id,
                "target": target.target,
                "task_id": task.id,
                "config": config,
                "passed": passed,
                "total_tokens": int(command_payload.get("total_tokens", 0)),
                "duration_ms": int(command_payload.get("duration_ms", elapsed_ms)),
                "skill_invoked": bool(command_payload.get("skill_invoked", config != "no-skill")),
                "error_type": error_type,
                "status": "completed",
            }

        return {
            "target_id": target.id,
            "target": target.target,
            "task_id": task.id,
            "config": config,
            "passed": False,
            "total_tokens": 0,
            "duration_ms": 0,
            "skill_invoked": False,
            "error_type": "missing_execution_config",
            "status": "incomplete",
        }

    def _extract_payload(self, stdout: str) -> dict[str, Any]:
        candidate = stdout.strip()
        if not candidate:
            return {}
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {}
        return {}
