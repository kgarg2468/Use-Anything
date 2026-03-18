#!/usr/bin/env python3
"""Deterministic verifier for one live benchmark run artifact."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from use_anything.benchmark.models import BenchmarkTask, BenchmarkTarget, load_benchmark_suite


def _find_target_task(suite_path: Path, target_id: str, task_id: str) -> tuple[BenchmarkTarget, BenchmarkTask]:
    suite = load_benchmark_suite(suite_path)
    for target in suite.targets:
        if target.id != target_id:
            continue
        for task in target.tasks:
            if task.id == task_id:
                return target, task
    raise ValueError(f"Could not find target={target_id} task={task_id} in suite {suite_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    target_id = os.environ.get("USE_ANYTHING_BENCH_TARGET_ID", "").strip()
    task_id = os.environ.get("USE_ANYTHING_BENCH_TASK_ID", "").strip()
    config = os.environ.get("USE_ANYTHING_BENCH_CONFIG", "").strip()

    if not target_id or not task_id or not config:
        raise SystemExit(2)

    suite_path = Path(args.suite).resolve()
    output_dir = Path(args.output_dir).resolve()

    _, task = _find_target_task(suite_path=suite_path, target_id=target_id, task_id=task_id)
    artifact_path = output_dir / "live-runs" / f"{args.run_id}__{target_id}__{task_id}__{config}.json"
    if not artifact_path.exists():
        raise SystemExit(1)

    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    response = str(payload.get("response", "")).strip()

    if payload.get("target_id") != target_id:
        raise SystemExit(1)
    if payload.get("task_id") != task_id:
        raise SystemExit(1)
    if payload.get("config") != config:
        raise SystemExit(1)
    if len(response) < 20:
        raise SystemExit(1)

    # Deterministic lexical check: at least one assertion keyword should be present when provided.
    if task.assertions:
        response_lower = response.lower()
        tokens = [token.lower().strip() for token in task.assertions if token.strip()]
        if tokens and not any(token in response_lower for token in tokens):
            raise SystemExit(1)

    raise SystemExit(0)


if __name__ == "__main__":
    main()
