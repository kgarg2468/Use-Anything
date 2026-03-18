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
        task_summary = self._compute_task_summary(records=records)
        config_stats = self._compute_config_stats(records=records, configs=configs)
        delta_vs_no_skill = self._compute_deltas(config_stats=config_stats)

        benchmark_summary = {
            "suite": suite.name,
            "agent": agent,
            "configs": configs,
            "total_runs": len(records),
            "completed_runs": completed_runs,
            "completion_rate": (completed_runs / len(records)) if records else 0.0,
            "config_stats": config_stats,
            "delta_vs_no_skill": delta_vs_no_skill,
        }

        (output_dir / "task_summary.json").write_text(json.dumps(task_summary, indent=2, sort_keys=True))
        (output_dir / "benchmark_summary.json").write_text(json.dumps(benchmark_summary, indent=2, sort_keys=True))
        (output_dir / "benchmark_report.md").write_text(
            self._render_report_markdown(
                suite_name=suite.name,
                benchmark_summary=benchmark_summary,
            )
        )

        return {
            "benchmark_summary": benchmark_summary,
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

    def _compute_config_stats(self, *, records: list[dict[str, Any]], configs: list[str]) -> dict[str, dict[str, float]]:
        stats: dict[str, dict[str, float]] = {}
        for config in configs:
            config_records = [
                record for record in records if record["config"] == config and record.get("status") == "completed"
            ]
            if not config_records:
                stats[config] = {
                    "count": 0.0,
                    "pass_rate": 0.0,
                    "tokens_mean": 0.0,
                    "duration_ms_mean": 0.0,
                    "skill_invocation_rate": 0.0,
                }
                continue

            count = float(len(config_records))
            pass_rate = sum(1 for record in config_records if record["passed"]) / count
            tokens_mean = sum(float(record["total_tokens"]) for record in config_records) / count
            duration_mean = sum(float(record["duration_ms"]) for record in config_records) / count
            invocation_rate = sum(1 for record in config_records if record["skill_invoked"]) / count

            stats[config] = {
                "count": count,
                "pass_rate": round(pass_rate, 4),
                "tokens_mean": round(tokens_mean, 4),
                "duration_ms_mean": round(duration_mean, 4),
                "skill_invocation_rate": round(invocation_rate, 4),
            }
        return stats

    def _compute_task_summary(self, *, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
        for record in records:
            key = (record["target_id"], record["target"], record["task_id"])
            entry = grouped.setdefault(
                key,
                {
                    "target_id": record["target_id"],
                    "target": record["target"],
                    "task_id": record["task_id"],
                    "configs": {},
                },
            )
            entry["configs"][record["config"]] = {
                "status": record["status"],
                "passed": record["passed"],
                "total_tokens": record["total_tokens"],
                "duration_ms": record["duration_ms"],
                "skill_invoked": record["skill_invoked"],
                "error_type": record["error_type"],
            }
        return sorted(grouped.values(), key=lambda item: (item["target_id"], item["task_id"]))

    def _compute_deltas(self, *, config_stats: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
        baseline = config_stats.get("no-skill", {})
        baseline_pass = float(baseline.get("pass_rate", 0.0))
        baseline_tokens = float(baseline.get("tokens_mean", 0.0))
        baseline_duration = float(baseline.get("duration_ms_mean", 0.0))

        deltas: dict[str, dict[str, float]] = {}
        for config, stats in config_stats.items():
            if config == "no-skill":
                continue
            deltas[config] = {
                "pass_rate_delta": round(float(stats["pass_rate"]) - baseline_pass, 4),
                "tokens_delta": round(float(stats["tokens_mean"]) - baseline_tokens, 4),
                "duration_ms_delta": round(float(stats["duration_ms_mean"]) - baseline_duration, 4),
            }
        return deltas

    def _render_report_markdown(self, *, suite_name: str, benchmark_summary: dict[str, Any]) -> str:
        lines = [
            f"# Benchmark Report: {suite_name}",
            "",
            f"- Total runs: {benchmark_summary['total_runs']}",
            f"- Completed runs: {benchmark_summary['completed_runs']}",
            f"- Completion rate: {benchmark_summary['completion_rate']:.4f}",
            "",
            "## Config Stats",
            "",
            "| Config | Pass Rate | Mean Tokens | Mean Duration (ms) | Skill Invocation |",
            "|---|---:|---:|---:|---:|",
        ]

        for config, stats in benchmark_summary["config_stats"].items():
            lines.append(
                f"| {config} | {stats['pass_rate']:.4f} | {stats['tokens_mean']:.4f} | "
                f"{stats['duration_ms_mean']:.4f} | {stats['skill_invocation_rate']:.4f} |"
            )

        lines.extend(
            [
                "",
                "## Delta vs No-Skill",
                "",
                "| Config | Pass Rate Delta | Tokens Delta | Duration Delta (ms) |",
                "|---|---:|---:|---:|",
            ]
        )
        for config, delta in benchmark_summary["delta_vs_no_skill"].items():
            lines.append(
                f"| {config} | {delta['pass_rate_delta']:.4f} | {delta['tokens_delta']:.4f} | "
                f"{delta['duration_ms_delta']:.4f} |"
            )

        lines.append("")
        return "\n".join(lines)
