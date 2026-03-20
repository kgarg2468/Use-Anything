#!/usr/bin/env python3
# ruff: noqa: E402,I001
"""Deterministic verifier for one live benchmark run artifact."""

from __future__ import annotations

import argparse
import json
import os
import re
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
    parser.add_argument("--run-id")
    args = parser.parse_args()

    target_id = os.environ.get("USE_ANYTHING_BENCH_TARGET_ID", "").strip()
    task_id = os.environ.get("USE_ANYTHING_BENCH_TASK_ID", "").strip()
    config = os.environ.get("USE_ANYTHING_BENCH_CONFIG", "").strip()
    run_id = (args.run_id or os.environ.get("USE_ANYTHING_BENCH_RUN_ID", "")).strip()

    if not target_id or not task_id or not config or not run_id:
        raise SystemExit(2)

    suite_path = Path(args.suite).resolve()
    output_dir_value = os.environ.get("USE_ANYTHING_BENCH_OUTPUT_DIR", "").strip() or str(args.output_dir).strip()
    output_dir = Path(output_dir_value).resolve()

    _, task = _find_target_task(suite_path=suite_path, target_id=target_id, task_id=task_id)
    artifact_path = output_dir / "live-runs" / f"{run_id}__{target_id}__{task_id}__{config}.json"
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

    required_evidence = [item.strip() for item in task.required_evidence if item.strip()]
    if required_evidence:
        if not _required_evidence_matched(required_evidence=required_evidence, response=response):
            raise SystemExit(1)
    elif task.assertions:
        # Fallback lexical check only when required evidence is not explicitly configured.
        response_lower = response.lower()
        keywords: set[str] = set()
        stopwords = {"without", "should", "their", "there", "about", "using", "include", "includes"}
        for assertion in task.assertions:
            for token in re.findall(r"[a-z0-9]+", assertion.lower()):
                if len(token) >= 5 and token not in stopwords:
                    keywords.add(token)

        if keywords and not any(keyword in response_lower for keyword in keywords):
            raise SystemExit(1)

    raise SystemExit(0)


def _required_evidence_matched(*, required_evidence: list[str], response: str) -> bool:
    matched = 0
    response_lower = response.lower()

    for rule in required_evidence:
        if rule.startswith("re:"):
            pattern = rule[3:]
            if pattern and re.search(pattern, response, flags=re.IGNORECASE):
                matched += 1
            continue

        if rule.lower() in response_lower:
            matched += 1

    required_matches = min(len(required_evidence), 2)
    return matched >= required_matches


if __name__ == "__main__":
    main()
