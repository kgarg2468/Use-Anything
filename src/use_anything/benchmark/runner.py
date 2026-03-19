"""Benchmark runner orchestration."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from use_anything.benchmark.models import BenchmarkSuite, BenchmarkTarget, BenchmarkTask


class BenchmarkRunner:
    """Run benchmark suites and return structured summaries."""

    GENERATED_SKILL_CONFIGS = {"generated-skill-default", "generated-skill-explicit"}
    SKILL_PATH_TEMPLATE_ENV = "USE_ANYTHING_BENCH_SKILL_PATH_TEMPLATE"
    DEFAULT_SKILL_PATH_TEMPLATE = "{workdir}/use-anything-{target_id}/SKILL.md"
    TASK_TIMEOUT_ENV = "USE_ANYTHING_BENCH_TASK_TIMEOUT_SECONDS"
    VERIFIER_TIMEOUT_ENV = "USE_ANYTHING_BENCH_VERIFIER_TIMEOUT_SECONDS"
    DEFAULT_TASK_TIMEOUT_SECONDS = 300
    DEFAULT_VERIFIER_TIMEOUT_SECONDS = 120

    def run(
        self,
        *,
        suite: BenchmarkSuite,
        output_dir: Path,
        configs: list[str],
        agent: str,
    ) -> dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)

        expected_runs = self._expected_runs(suite=suite, configs=configs)
        preflight = self._preflight_validate(suite=suite, configs=configs, output_dir=output_dir)

        if not preflight["passed"]:
            benchmark_summary = self._build_summary(
                suite_name=suite.name,
                agent=agent,
                configs=configs,
                total_runs=expected_runs,
                completed_runs=0,
                records=[],
                preflight=preflight,
            )
            self._write_artifacts(output_dir=output_dir, records=[], benchmark_summary=benchmark_summary)
            return {
                "benchmark_summary": benchmark_summary,
                "output_dir": str(output_dir),
            }

        records: list[dict[str, Any]] = []
        for target in suite.targets:
            for task in target.tasks:
                for config in configs:
                    records.append(
                        self._execute_task(
                            target=target,
                            task=task,
                            config=config,
                            output_dir=output_dir,
                        )
                    )

        completed_runs = sum(1 for record in records if record["status"] == "completed")
        benchmark_summary = self._build_summary(
            suite_name=suite.name,
            agent=agent,
            configs=configs,
            total_runs=len(records),
            completed_runs=completed_runs,
            records=records,
            preflight=preflight,
        )
        self._write_artifacts(output_dir=output_dir, records=records, benchmark_summary=benchmark_summary)
        return {
            "benchmark_summary": benchmark_summary,
            "output_dir": str(output_dir),
        }

    def _build_summary(
        self,
        *,
        suite_name: str,
        agent: str,
        configs: list[str],
        total_runs: int,
        completed_runs: int,
        records: list[dict[str, Any]],
        preflight: dict[str, Any],
    ) -> dict[str, Any]:
        config_stats = self._compute_config_stats(records=records, configs=configs)
        delta_vs_no_skill = self._compute_deltas(config_stats=config_stats)
        runtime_incomplete = self._count_reasons_from_records(records)
        preflight_incomplete = self._count_reasons_from_issues(preflight["missing_matrix"])
        incomplete_reason_counts = self._merge_reason_counts(preflight_incomplete, runtime_incomplete)

        return {
            "suite": suite_name,
            "agent": agent,
            "configs": configs,
            "total_runs": total_runs,
            "completed_runs": completed_runs,
            "completion_rate": (completed_runs / total_runs) if total_runs else 0.0,
            "config_stats": config_stats,
            "delta_vs_no_skill": delta_vs_no_skill,
            "preflight": preflight,
            "incomplete_reason_counts": incomplete_reason_counts,
        }

    def _write_artifacts(
        self,
        *,
        output_dir: Path,
        records: list[dict[str, Any]],
        benchmark_summary: dict[str, Any],
    ) -> None:
        raw_path = output_dir / "raw_runs.jsonl"
        raw_path.write_text("".join(json.dumps(record, sort_keys=True) + "\n" for record in records))

        task_summary = self._compute_task_summary(records=records)
        (output_dir / "task_summary.json").write_text(json.dumps(task_summary, indent=2, sort_keys=True))
        (output_dir / "benchmark_summary.json").write_text(json.dumps(benchmark_summary, indent=2, sort_keys=True))
        (output_dir / "benchmark_report.md").write_text(
            self._render_report_markdown(
                suite_name=str(benchmark_summary["suite"]),
                benchmark_summary=benchmark_summary,
            )
        )

    def _expected_runs(self, *, suite: BenchmarkSuite, configs: list[str]) -> int:
        return sum(len(target.tasks) for target in suite.targets) * len(configs)

    def _preflight_validate(
        self,
        *,
        suite: BenchmarkSuite,
        configs: list[str],
        output_dir: Path,
    ) -> dict[str, Any]:
        missing_matrix: list[dict[str, str]] = []
        for target in suite.targets:
            for task in target.tasks:
                for config in configs:
                    has_replay = config in task.replay_results
                    has_command = bool(task.commands.get(config))

                    if not has_replay and not has_command:
                        missing_matrix.append(
                            {
                                "target_id": target.id,
                                "task_id": task.id,
                                "config": config,
                                "reason": "missing_execution_config",
                            }
                        )

                    if has_command and not task.verifier_command:
                        missing_matrix.append(
                            {
                                "target_id": target.id,
                                "task_id": task.id,
                                "config": config,
                                "reason": "missing_verifier_command",
                            }
                        )

                    if has_command and config in self.GENERATED_SKILL_CONFIGS:
                        skill_path = self._resolve_generated_skill_path(
                            target=target,
                            task=task,
                            config=config,
                            output_dir=output_dir,
                        )
                        if not skill_path.exists():
                            missing_matrix.append(
                                {
                                    "target_id": target.id,
                                    "task_id": task.id,
                                    "config": config,
                                    "reason": "missing_generated_skill_context",
                                }
                            )

        return {
            "passed": not missing_matrix,
            "missing_matrix": missing_matrix,
        }

    def _execute_task(
        self,
        *,
        target: BenchmarkTarget,
        task: BenchmarkTask,
        config: str,
        output_dir: Path,
    ) -> dict[str, Any]:
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
            run_id = f"{int(time.time() * 1000)}-{target.id}-{task.id}-{config}"
            env = self._build_execution_env(
                target=target,
                task=task,
                config=config,
                output_dir=output_dir,
                run_id=run_id,
            )
            start = time.perf_counter()
            task_timeout_seconds = self._timeout_seconds(
                env_name=self.TASK_TIMEOUT_ENV,
                default=self.DEFAULT_TASK_TIMEOUT_SECONDS,
            )
            try:
                completed = subprocess.run(
                    command,
                    shell=True,
                    cwd=task.workdir or None,
                    capture_output=True,
                    text=True,
                    check=False,
                    env=env,
                    timeout=task_timeout_seconds,
                )
            except subprocess.TimeoutExpired:
                elapsed_ms = int((time.perf_counter() - start) * 1000)
                return {
                    "target_id": target.id,
                    "target": target.target,
                    "task_id": task.id,
                    "config": config,
                    "run_id": run_id,
                    "passed": False,
                    "total_tokens": 0,
                    "duration_ms": elapsed_ms,
                    "skill_invoked": bool(config != "no-skill"),
                    "error_type": "command_timeout",
                    "status": "completed",
                }
            command_payload = self._extract_payload(completed.stdout)
            passed = bool(command_payload.get("passed", completed.returncode == 0))
            error_type = command_payload.get("error_type")
            if completed.returncode != 0:
                passed = False

            if task.verifier_command:
                verifier_timeout_seconds = self._timeout_seconds(
                    env_name=self.VERIFIER_TIMEOUT_ENV,
                    default=self.DEFAULT_VERIFIER_TIMEOUT_SECONDS,
                )
                try:
                    verifier = subprocess.run(
                        task.verifier_command,
                        shell=True,
                        cwd=task.workdir or None,
                        capture_output=True,
                        text=True,
                        check=False,
                        env=env,
                        timeout=verifier_timeout_seconds,
                    )
                except subprocess.TimeoutExpired:
                    passed = False
                    error_type = "verification_timeout"
                else:
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
                "run_id": run_id,
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

    def _build_execution_env(
        self,
        *,
        target: BenchmarkTarget,
        task: BenchmarkTask,
        config: str,
        output_dir: Path,
        run_id: str,
    ) -> dict[str, str]:
        env = dict(os.environ)
        env["USE_ANYTHING_BENCH_TARGET_ID"] = target.id
        env["USE_ANYTHING_BENCH_TARGET"] = target.target
        env["USE_ANYTHING_BENCH_TASK_ID"] = task.id
        env["USE_ANYTHING_BENCH_CONFIG"] = config
        env["USE_ANYTHING_BENCH_OUTPUT_DIR"] = str(output_dir)
        env["USE_ANYTHING_BENCH_WORKDIR"] = str(
            Path(task.workdir).expanduser().resolve() if task.workdir else Path.cwd().resolve()
        )
        env["USE_ANYTHING_BENCH_RUN_ID"] = run_id
        env["USE_ANYTHING_BENCH_SKILL_PATH"] = str(
            self._resolve_generated_skill_path(
                target=target,
                task=task,
                config=config,
                output_dir=output_dir,
            )
        )
        return env

    def _resolve_generated_skill_path(
        self,
        *,
        target: BenchmarkTarget,
        task: BenchmarkTask,
        config: str,
        output_dir: Path,
    ) -> Path:
        workdir = Path(task.workdir).expanduser().resolve() if task.workdir else Path.cwd().resolve()
        template = os.environ.get(self.SKILL_PATH_TEMPLATE_ENV, self.DEFAULT_SKILL_PATH_TEMPLATE)
        try:
            rendered = template.format(
                target_id=target.id,
                target=target.target,
                config=config,
                output_dir=str(output_dir.resolve()),
                workdir=str(workdir),
            )
        except (KeyError, ValueError):
            rendered = self.DEFAULT_SKILL_PATH_TEMPLATE.format(
                target_id=target.id,
                target=target.target,
                config=config,
                output_dir=str(output_dir.resolve()),
                workdir=str(workdir),
            )

        resolved = Path(rendered).expanduser()
        if not resolved.is_absolute():
            resolved = workdir / resolved
        return resolved.resolve()

    def _timeout_seconds(self, *, env_name: str, default: int) -> int:
        raw = os.environ.get(env_name, "").strip()
        if not raw:
            return default
        try:
            parsed = int(raw)
        except ValueError:
            return default
        return parsed if parsed > 0 else default

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

    def _compute_config_stats(
        self,
        *,
        records: list[dict[str, Any]],
        configs: list[str],
    ) -> dict[str, dict[str, float]]:
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

    def _count_reasons_from_records(self, records: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for record in records:
            if record.get("status") != "incomplete":
                continue
            reason = str(record.get("error_type") or "unknown")
            counts[reason] = counts.get(reason, 0) + 1
        return counts

    def _count_reasons_from_issues(self, issues: list[dict[str, str]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for issue in issues:
            reason = issue.get("reason", "unknown")
            counts[reason] = counts.get(reason, 0) + 1
        return counts

    def _merge_reason_counts(self, left: dict[str, int], right: dict[str, int]) -> dict[str, int]:
        merged = dict(left)
        for reason, count in right.items():
            merged[reason] = merged.get(reason, 0) + count
        return merged

    def _render_report_markdown(self, *, suite_name: str, benchmark_summary: dict[str, Any]) -> str:
        lines = [
            f"# Benchmark Report: {suite_name}",
            "",
            f"- Total runs: {benchmark_summary['total_runs']}",
            f"- Completed runs: {benchmark_summary['completed_runs']}",
            f"- Completion rate: {benchmark_summary['completion_rate']:.4f}",
            f"- Preflight passed: {benchmark_summary['preflight']['passed']}",
            "",
            "## Incomplete Reason Counts",
            "",
        ]

        reason_counts = benchmark_summary.get("incomplete_reason_counts", {})
        if reason_counts:
            for reason, count in sorted(reason_counts.items()):
                lines.append(f"- {reason}: {count}")
        else:
            lines.append("- none")

        lines.extend(
            [
                "",
                "## Config Stats",
                "",
                "| Config | Pass Rate | Mean Tokens | Mean Duration (ms) | Skill Invocation |",
                "|---|---:|---:|---:|---:|",
            ]
        )

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
