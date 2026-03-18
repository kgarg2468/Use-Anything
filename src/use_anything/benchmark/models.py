"""Dataclasses and schema parsing for benchmark suites."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

BenchmarkConfig = Literal[
    "no-skill",
    "generated-skill-default",
    "generated-skill-explicit",
    "agents-md-doc-index",
]

DEFAULT_BENCHMARK_CONFIGS: list[str] = [
    "no-skill",
    "generated-skill-default",
    "generated-skill-explicit",
    "agents-md-doc-index",
]


@dataclass
class BenchmarkTask:
    id: str
    prompt: str
    expected_output: str
    assertions: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    commands: dict[str, str] = field(default_factory=dict)
    replay_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    verifier_command: str | None = None
    workdir: str | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> BenchmarkTask:
        task_id = _require_non_empty_string(raw, "id", context="task")
        prompt = _require_non_empty_string(raw, "prompt", context=f"task '{task_id}'")
        expected_output = _require_non_empty_string(raw, "expected_output", context=f"task '{task_id}'")

        assertions = _list_of_strings(raw.get("assertions", []), field_name="assertions", context=f"task '{task_id}'")
        files = _list_of_strings(raw.get("files", []), field_name="files", context=f"task '{task_id}'")
        commands = _dict_of_strings(raw.get("commands", {}), field_name="commands", context=f"task '{task_id}'")

        replay_results_raw = raw.get("replay_results", {})
        if not isinstance(replay_results_raw, dict):
            raise ValueError(f"task '{task_id}': replay_results must be an object")
        replay_results: dict[str, dict[str, Any]] = {}
        for config_name, payload in replay_results_raw.items():
            if not isinstance(config_name, str) or not config_name.strip():
                raise ValueError(f"task '{task_id}': replay_results keys must be non-empty strings")
            if not isinstance(payload, dict):
                raise ValueError(f"task '{task_id}': replay_results['{config_name}'] must be an object")
            replay_results[config_name] = payload

        verifier_command = raw.get("verifier_command")
        if verifier_command is not None and not isinstance(verifier_command, str):
            raise ValueError(f"task '{task_id}': verifier_command must be a string")

        workdir = raw.get("workdir")
        if workdir is not None and not isinstance(workdir, str):
            raise ValueError(f"task '{task_id}': workdir must be a string")

        return cls(
            id=task_id,
            prompt=prompt,
            expected_output=expected_output,
            assertions=assertions,
            files=files,
            commands=commands,
            replay_results=replay_results,
            verifier_command=verifier_command,
            workdir=workdir,
        )


@dataclass
class BenchmarkTarget:
    id: str
    target: str
    tasks: list[BenchmarkTask]

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> BenchmarkTarget:
        target_id = _require_non_empty_string(raw, "id", context="target")
        target_value = _require_non_empty_string(raw, "target", context=f"target '{target_id}'")

        tasks_raw = raw.get("tasks")
        if not isinstance(tasks_raw, list) or not tasks_raw:
            raise ValueError(f"target '{target_id}': tasks must be a non-empty list")

        tasks: list[BenchmarkTask] = []
        for task_raw in tasks_raw:
            if not isinstance(task_raw, dict):
                raise ValueError(f"target '{target_id}': each task must be an object")
            tasks.append(BenchmarkTask.from_dict(task_raw))

        return cls(id=target_id, target=target_value, tasks=tasks)


@dataclass
class BenchmarkSuite:
    name: str
    agent: str
    optimization_goal: str
    configs: list[str]
    targets: list[BenchmarkTarget]
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> BenchmarkSuite:
        name = _require_non_empty_string(raw, "name", context="suite")

        agent_raw = raw.get("agent", "codex")
        if not isinstance(agent_raw, str) or not agent_raw.strip():
            raise ValueError("suite: agent must be a non-empty string")
        agent = agent_raw.strip().lower()

        optimization_goal_raw = raw.get("optimization_goal", "accuracy-first")
        if not isinstance(optimization_goal_raw, str) or not optimization_goal_raw.strip():
            raise ValueError("suite: optimization_goal must be a non-empty string")

        configs_raw = raw.get("configs", DEFAULT_BENCHMARK_CONFIGS)
        configs = _list_of_strings(configs_raw, field_name="configs", context="suite")
        if not configs:
            raise ValueError("suite: configs must include at least one config")

        unknown = [config for config in configs if config not in DEFAULT_BENCHMARK_CONFIGS]
        if unknown:
            raise ValueError(
                "suite: unknown config(s): "
                f"{', '.join(sorted(unknown))}. "
                f"Allowed: {', '.join(DEFAULT_BENCHMARK_CONFIGS)}"
            )

        targets_raw = raw.get("targets")
        if not isinstance(targets_raw, list) or not targets_raw:
            raise ValueError("suite: targets must be a non-empty list")

        targets: list[BenchmarkTarget] = []
        for target_raw in targets_raw:
            if not isinstance(target_raw, dict):
                raise ValueError("suite: each target must be an object")
            targets.append(BenchmarkTarget.from_dict(target_raw))

        metadata = raw.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ValueError("suite: metadata must be an object")

        return cls(
            name=name,
            agent=agent,
            optimization_goal=str(optimization_goal_raw).strip(),
            configs=configs,
            targets=targets,
            metadata=metadata,
        )

    @property
    def task_count(self) -> int:
        return sum(len(target.tasks) for target in self.targets)


def load_benchmark_suite(path: Path | str) -> BenchmarkSuite:
    suite_path = Path(path)
    if not suite_path.exists():
        raise ValueError(f"suite file not found: {suite_path}")

    try:
        raw = json.loads(suite_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid benchmark suite JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError("suite root must be a JSON object")

    return BenchmarkSuite.from_dict(raw)


def _require_non_empty_string(raw: dict[str, Any], key: str, *, context: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context}: {key} must be a non-empty string")
    return value.strip()


def _list_of_strings(value: Any, *, field_name: str, context: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{context}: {field_name} must be a list")

    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{context}: all values in {field_name} must be strings")
        stripped = item.strip()
        if not stripped:
            raise ValueError(f"{context}: {field_name} cannot contain empty strings")
        out.append(stripped)
    return out


def _dict_of_strings(value: Any, *, field_name: str, context: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(f"{context}: {field_name} must be an object")

    out: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"{context}: {field_name} keys must be non-empty strings")
        if not isinstance(item, str):
            raise ValueError(f"{context}: {field_name} values must be strings")
        out[key.strip()] = item
    return out
