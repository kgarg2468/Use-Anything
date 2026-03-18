#!/usr/bin/env python3
# ruff: noqa: E402,I001
"""Orchestrate Benchmark 1 reruns with archive + pilot gate + full run."""

from __future__ import annotations

import argparse
import json
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


def _archive_existing_outputs(output_dir: Path) -> Path | None:
    output_dir.mkdir(parents=True, exist_ok=True)
    existing: list[Path] = []

    for name in ARTIFACT_NAMES:
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
    args = parser.parse_args()

    suite_path = Path(args.suite).resolve()
    output_dir = Path(args.output_dir).resolve()

    full_suite = load_benchmark_suite(suite_path)
    archive_dir = _archive_existing_outputs(output_dir)

    pilot_suite = _pilot_suite(full_suite=full_suite, pilot_targets=max(1, args.pilot_targets))
    pilot_result = BenchmarkRunner().run(
        suite=pilot_suite,
        output_dir=output_dir,
        configs=list(full_suite.configs),
        agent=args.agent,
    )
    pilot_summary = pilot_result["benchmark_summary"]

    response: dict[str, object] = {
        "archive_dir": str(archive_dir) if archive_dir else None,
        "pilot_summary": pilot_summary,
        "output_dir": str(output_dir),
    }

    if not _pilot_gate_passed(pilot_summary):
        response["status"] = "pilot_failed"
        print(json.dumps(response, indent=2))
        raise SystemExit(1)

    if args.skip_full_run:
        response["status"] = "pilot_passed_full_skipped"
        print(json.dumps(response, indent=2))
        raise SystemExit(0)

    full_result = BenchmarkRunner().run(
        suite=full_suite,
        output_dir=output_dir,
        configs=list(full_suite.configs),
        agent=args.agent,
    )
    response["status"] = "full_completed"
    response["full_summary"] = full_result["benchmark_summary"]
    print(json.dumps(response, indent=2))


if __name__ == "__main__":
    main()
