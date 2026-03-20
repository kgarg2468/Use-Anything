#!/usr/bin/env python3
"""Populate required_evidence fields for benchmark tasks deterministically."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "for",
    "from",
    "the",
    "this",
    "that",
    "with",
    "without",
    "using",
    "use",
    "run",
    "task",
    "workflow",
}


def _keyword_tokens(text: str, *, min_len: int) -> list[str]:
    out: list[str] = []
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        if len(token) < min_len or token in STOPWORDS:
            continue
        if token not in out:
            out.append(token)
    return out


def _derive_required_evidence(*, target_id: str, task: dict[str, Any]) -> list[str]:
    evidence: list[str] = []
    target_norm = target_id.strip().lower()
    if target_norm:
        evidence.append(target_norm)

    task_id = str(task.get("id", "")).strip().lower()
    task_suffix = task_id
    if task_suffix.startswith(f"{target_norm}-"):
        task_suffix = task_suffix[len(target_norm) + 1 :]
    task_id_tokens = [token for token in task_suffix.replace("_", "-").split("-") if token and token not in STOPWORDS]
    evidence.extend(task_id_tokens[:2])

    prompt_tokens = _keyword_tokens(str(task.get("prompt", "")), min_len=5)
    expected_tokens = _keyword_tokens(str(task.get("expected_output", "")), min_len=5)
    for token in [*prompt_tokens, *expected_tokens]:
        evidence.append(token)
        if len(evidence) >= 4:
            break

    deduped: list[str] = []
    for item in evidence:
        if item and item not in deduped:
            deduped.append(item)
    return deduped[:4]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", default="benchmark/comprehensive-codex-suite.json")
    args = parser.parse_args()

    suite_path = Path(args.suite).resolve()
    payload = json.loads(suite_path.read_text(encoding="utf-8"))
    targets = payload.get("targets", [])
    if not isinstance(targets, list):
        raise SystemExit("suite targets must be a list")

    for target in targets:
        if not isinstance(target, dict):
            continue
        target_id = str(target.get("id", "")).strip()
        tasks = target.get("tasks", [])
        if not isinstance(tasks, list):
            continue
        for task in tasks:
            if not isinstance(task, dict):
                continue
            task["required_evidence"] = _derive_required_evidence(target_id=target_id, task=task)

    suite_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
