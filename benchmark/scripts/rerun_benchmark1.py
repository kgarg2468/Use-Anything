#!/usr/bin/env python3
# ruff: noqa: E402,I001
"""Orchestrate Benchmark 1 reruns with archive + pilot gate + full run."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from use_anything.benchmark.models import BenchmarkSuite, load_benchmark_suite
from use_anything.benchmark.runner import BenchmarkRunner

ARTIFACT_NAMES = [
    "raw_runs.jsonl",
    "task_summary.json",
    "benchmark_summary.json",
    "benchmark_report.md",
]
AUXILIARY_STATUS_FILES = [
    "orchestrator-status.txt",
    "rerun.pid",
    "run-progress.md",
    "rerun-live.log",
]


def _archive_existing_outputs(output_dir: Path) -> Path | None:
    output_dir.mkdir(parents=True, exist_ok=True)
    existing: list[Path] = []

    for name in ARTIFACT_NAMES:
        path = output_dir / name
        if path.exists():
            existing.append(path)

    for name in AUXILIARY_STATUS_FILES:
        path = output_dir / name
        if path.exists():
            existing.append(path)

    live_runs = output_dir / "live-runs"
    if live_runs.exists():
        existing.append(live_runs)

    if not existing:
        return None

    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    archive_dir = output_dir / "archive" / timestamp
    archive_dir.mkdir(parents=True, exist_ok=True)

    for path in existing:
        shutil.move(str(path), str(archive_dir / path.name))

    return archive_dir


def _append_live_log(output_dir: Path, message: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).isoformat()
    line = f"{timestamp} {message}\n"
    with (output_dir / "rerun-live.log").open("a", encoding="utf-8") as handle:
        handle.write(line)


def _write_status(output_dir: Path, *, status: str, detail: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).isoformat()
    (output_dir / "orchestrator-status.txt").write_text(
        f"status={status}\ndetail={detail}\nupdated_at={timestamp}\n",
        encoding="utf-8",
    )
    (output_dir / "run-progress.md").write_text(
        "\n".join(
            [
                "# Benchmark Rerun Status",
                "",
                f"- status: {status}",
                f"- detail: {detail}",
                f"- updated_at: {timestamp}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _append_live_log(output_dir, f"status={status} detail={detail}")


def _write_pid(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "rerun.pid").write_text(f"{os.getpid()}\n", encoding="utf-8")


def _clear_pid(output_dir: Path) -> None:
    (output_dir / "rerun.pid").unlink(missing_ok=True)


def _pilot_suite(full_suite: BenchmarkSuite, pilot_targets: int) -> BenchmarkSuite:
    payload = {
        "name": f"{full_suite.name}-pilot",
        "agent": full_suite.agent,
        "optimization_goal": full_suite.optimization_goal,
        "configs": list(full_suite.configs),
        "metadata": dict(full_suite.metadata),
        "targets": [
            {
                "id": target.id,
                "target": target.target,
                "tasks": [
                    {
                        "id": task.id,
                        "prompt": task.prompt,
                        "expected_output": task.expected_output,
                        "assertions": task.assertions,
                        "files": task.files,
                        "commands": task.commands,
                        "replay_results": task.replay_results,
                        "verifier_command": task.verifier_command,
                        "workdir": task.workdir,
                    }
                    for task in target.tasks
                ],
            }
            for target in full_suite.targets[:pilot_targets]
        ],
    }
    return BenchmarkSuite.from_dict(payload)


def _pilot_gate_passed(summary: dict) -> bool:
    completion = float(summary.get("completion_rate", 0.0))
    missing_exec = int(summary.get("incomplete_reason_counts", {}).get("missing_execution_config", 0))
    return completion >= 0.95 and missing_exec == 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", default=str(ROOT / "benchmark" / "comprehensive-codex-suite.json"))
    parser.add_argument("--output-dir", default=str(ROOT / "benchmark" / "benchmark-1-run"))
    parser.add_argument("--agent", default="codex")
    parser.add_argument("--pilot-targets", type=int, default=2)
    parser.add_argument("--skip-full-run", action="store_true")
    parser.add_argument("--task-timeout-seconds", type=int)
    parser.add_argument("--verifier-timeout-seconds", type=int)
    args = parser.parse_args()

    suite_path = Path(args.suite).resolve()
    output_dir = Path(args.output_dir).resolve()

    archive_dir = _archive_existing_outputs(output_dir)
    _write_pid(output_dir)
    _write_status(output_dir, status="running", detail="starting rerun")

    try:
        full_suite = load_benchmark_suite(suite_path)
        pilot_suite = _pilot_suite(full_suite=full_suite, pilot_targets=max(1, args.pilot_targets))
        pilot_result = BenchmarkRunner().run(
            suite=pilot_suite,
            output_dir=output_dir,
            configs=list(full_suite.configs),
            agent=args.agent,
            task_timeout_seconds=args.task_timeout_seconds,
            verifier_timeout_seconds=args.verifier_timeout_seconds,
        )
        pilot_summary = pilot_result["benchmark_summary"]

        response: dict[str, object] = {
            "archive_dir": str(archive_dir) if archive_dir else None,
            "pilot_summary": pilot_summary,
            "output_dir": str(output_dir),
        }

        if not _pilot_gate_passed(pilot_summary):
            response["status"] = "pilot_failed"
            _write_status(output_dir, status="failed", detail="pilot_failed")
            print(json.dumps(response, indent=2))
            raise SystemExit(1)

        if args.skip_full_run:
            response["status"] = "pilot_passed_full_skipped"
            _write_status(output_dir, status="completed", detail="pilot_passed_full_skipped")
            print(json.dumps(response, indent=2))
            raise SystemExit(0)

        full_result = BenchmarkRunner().run(
            suite=full_suite,
            output_dir=output_dir,
            configs=list(full_suite.configs),
            agent=args.agent,
            task_timeout_seconds=args.task_timeout_seconds,
            verifier_timeout_seconds=args.verifier_timeout_seconds,
        )
        response["status"] = "full_completed"
        response["full_summary"] = full_result["benchmark_summary"]
        _write_status(output_dir, status="completed", detail="full_completed")
        print(json.dumps(response, indent=2))
    except Exception:
        _write_status(output_dir, status="failed", detail="unexpected_exception")
        raise
    finally:
        _clear_pid(output_dir)


if __name__ == "__main__":
    main()
