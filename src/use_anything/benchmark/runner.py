"""Benchmark runner orchestration."""

from __future__ import annotations

import json
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
        if payload is None:
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
