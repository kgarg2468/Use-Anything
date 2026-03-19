#!/usr/bin/env python3
# ruff: noqa: E402,I001
"""Execute one live benchmark task and emit strict JSON output."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from use_anything.benchmark.models import BenchmarkTask, BenchmarkTarget, load_benchmark_suite


def _estimate_tokens(*parts: str) -> int:
    return sum(len(part.split()) for part in parts if part)


def _find_target_task(suite_path: Path, target_id: str, task_id: str) -> tuple[BenchmarkTarget, BenchmarkTask]:
    suite = load_benchmark_suite(suite_path)
    for target in suite.targets:
        if target.id != target_id:
            continue
        for task in target.tasks:
            if task.id == task_id:
                return target, task
    raise ValueError(f"Could not find target={target_id} task={task_id} in suite {suite_path}")


def _read_optional(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _build_prompt(
    *,
    target: BenchmarkTarget,
    task: BenchmarkTask,
    config: str,
    workdir: Path,
) -> str:
    sections: list[str] = []
    sections.append(f"Target: {target.target} ({target.id})")
    sections.append(f"Task ID: {task.id}")
    sections.append(f"Prompt: {task.prompt}")
    sections.append(f"Expected output: {task.expected_output}")
    if task.assertions:
        sections.append("Assertions:\n- " + "\n- ".join(task.assertions))

    skill_path = _resolve_skill_path(target=target, workdir=workdir)
    agents_md_path = workdir / "AGENTS.md"

    if config == "no-skill":
        sections.append("Config: no-skill. Use only task prompt and normal reasoning.")
    elif config == "generated-skill-default":
        sections.append("Config: generated-skill-default. Generated skill context (optional use):")
        skill_text = _read_optional(skill_path)
        if skill_text:
            sections.append(skill_text[:6000])
        else:
            sections.append(f"No generated skill file found at {skill_path}")
    elif config == "generated-skill-explicit":
        sections.append("Config: generated-skill-explicit. You MUST apply generated skill guidance.")
        skill_text = _read_optional(skill_path)
        if skill_text:
            sections.append(skill_text[:6000])
        else:
            sections.append(f"No generated skill file found at {skill_path}")
    elif config == "agents-md-doc-index":
        sections.append("Config: agents-md-doc-index. Use AGENTS.md/doc index context only.")
        agents_text = _read_optional(agents_md_path)
        if agents_text:
            sections.append(agents_text[:6000])
        else:
            sections.append(f"No AGENTS.md found at {agents_md_path}")
    else:
        sections.append(f"Config: {config}")

    sections.append("Return a concise practical answer for this task.")
    return "\n\n".join(sections)


def _resolve_skill_path(*, target: BenchmarkTarget, workdir: Path) -> Path:
    env_path = os.environ.get("USE_ANYTHING_BENCH_SKILL_PATH", "").strip()
    if env_path:
        candidate = Path(env_path).expanduser()
        if not candidate.is_absolute():
            candidate = workdir / candidate
        return candidate.resolve()
    return (ROOT / f"use-anything-{target.id}" / "SKILL.md").resolve()


def _execute_codex(prompt: str, workdir: Path, timeout_seconds: int) -> tuple[int, str, str | None]:
    codex = shutil.which("codex")
    if not codex:
        return 2, "", "codex_not_found"

    with tempfile.NamedTemporaryFile(prefix="use-anything-bench-", suffix=".txt", delete=False) as handle:
        output_file = Path(handle.name)

    command = [
        codex,
        "exec",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "--output-last-message",
        str(output_file),
        prompt,
    ]

    try:
        completed = subprocess.run(
            command,
            cwd=str(workdir),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        output_file.unlink(missing_ok=True)
        return 124, "", "codex_exec_timeout"

    response = output_file.read_text(encoding="utf-8").strip() if output_file.exists() else ""
    output_file.unlink(missing_ok=True)

    error_type = None
    if completed.returncode != 0:
        error_type = "codex_exec_failed"

    return completed.returncode, response, error_type


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", required=True)
    parser.add_argument("--target-id", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--workdir")
    parser.add_argument("--output-dir")
    args = parser.parse_args()

    suite_path = Path(args.suite).resolve()
    workdir_value = os.environ.get("USE_ANYTHING_BENCH_WORKDIR", "").strip() or (args.workdir or "").strip()
    output_dir_value = os.environ.get("USE_ANYTHING_BENCH_OUTPUT_DIR", "").strip() or (args.output_dir or "").strip()
    if not workdir_value or not output_dir_value:
        raise SystemExit(2)

    workdir = Path(workdir_value).resolve()
    output_dir = Path(output_dir_value).resolve()
    run_id = args.run_id or os.environ.get("USE_ANYTHING_BENCH_RUN_ID") or str(int(time.time() * 1000))

    target, task = _find_target_task(suite_path=suite_path, target_id=args.target_id, task_id=args.task_id)
    prompt = _build_prompt(target=target, task=task, config=args.config, workdir=workdir)

    start = time.perf_counter()
    use_fake = str(os.environ.get("USE_ANYTHING_BENCH_FAKE", "0")).strip().lower() in {
        "1",
        "true",
        "yes",
    }

    if use_fake:
        response = f"{target.id} workflow output for {task.id} using {args.config}."
        returncode = 0
        error_type = None
    else:
        timeout_raw = os.environ.get("USE_ANYTHING_BENCH_CODEX_TIMEOUT_SECONDS", "").strip()
        try:
            timeout_seconds = int(timeout_raw) if timeout_raw else 240
        except ValueError:
            timeout_seconds = 240
        if timeout_seconds <= 0:
            timeout_seconds = 240
        returncode, response, error_type = _execute_codex(
            prompt=prompt,
            workdir=workdir,
            timeout_seconds=timeout_seconds,
        )

    duration_ms = int((time.perf_counter() - start) * 1000)
    passed = returncode == 0 and bool(response)
    skill_invoked = {
        "no-skill": False,
        "generated-skill-default": "skill" in response.lower(),
        "generated-skill-explicit": True,
        "agents-md-doc-index": False,
    }.get(args.config, False)

    total_tokens = _estimate_tokens(prompt, response)

    artifact = {
        "run_id": run_id,
        "target_id": args.target_id,
        "task_id": args.task_id,
        "config": args.config,
        "passed": passed,
        "duration_ms": duration_ms,
        "total_tokens": total_tokens,
        "skill_invoked": skill_invoked,
        "error_type": error_type,
        "prompt": prompt,
        "response": response,
    }

    live_dir = output_dir / "live-runs"
    live_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = live_dir / f"{run_id}__{args.target_id}__{args.task_id}__{args.config}.json"
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")

    payload = {
        "passed": passed,
        "total_tokens": total_tokens,
        "duration_ms": duration_ms,
        "skill_invoked": skill_invoked,
    }
    if error_type:
        payload["error_type"] = error_type

    print(json.dumps(payload))


if __name__ == "__main__":
    main()
