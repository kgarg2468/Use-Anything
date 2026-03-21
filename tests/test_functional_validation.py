from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from use_anything.models import AnalyzerIR, GeneratedArtifacts
from use_anything.validate.functional import run_functional_validation


def _analysis() -> AnalyzerIR:
    return AnalyzerIR.from_dict(
        {
            "software": "demo",
            "interface": "python_sdk",
            "version": "1.0",
            "setup": {
                "install": "pip install demo",
                "auth": "Set DEMO_API_KEY",
                "env_vars": ["DEMO_API_KEY"],
                "prerequisites": [],
            },
            "capability_groups": [],
            "workflows": [
                {
                    "name": "Run smoke",
                    "steps": ["python -c \"print('ok')\""],
                    "common_errors": [],
                }
            ],
            "gotchas": ["x", "y", "z", "a", "b"],
            "analysis_sources": ["python_sdk:pypi:demo"],
        }
    )


def test_functional_validation_runs_checks_in_order(tmp_path: Path) -> None:
    calls: list[str] = []

    def fake_runner(command: str, *, timeout_seconds: int):
        calls.append(command)
        return 0, "ok", ""

    script_path = tmp_path / "scripts" / "verify_setup.py"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text("print('ok')\n")
    artifacts = GeneratedArtifacts(
        skill_path=tmp_path / "SKILL.md",
        reference_paths={},
        token_counts={},
        line_counts={},
        script_paths={"verify_setup": script_path},
    )

    report = run_functional_validation(
        analysis=_analysis(),
        artifacts=artifacts,
        timeout_seconds=12,
        command_runner=fake_runner,
    )

    assert report.enabled is True
    assert report.passed is True
    assert [step.name for step in report.steps] == [
        "setup_install",
        "verify_setup_script",
        "workflow_first_step",
    ]
    assert calls[0] == "pip install demo"
    assert "verify_setup.py" in calls[1]
    assert calls[2] == "python -c \"print('ok')\""


def test_functional_validation_records_timeout_failure(tmp_path: Path) -> None:
    def fake_runner(command: str, *, timeout_seconds: int):  # noqa: ARG001
        raise subprocess.TimeoutExpired(command, timeout=timeout_seconds)

    artifacts = GeneratedArtifacts(
        skill_path=tmp_path / "SKILL.md",
        reference_paths={},
        token_counts={},
        line_counts={},
        script_paths={},
    )

    report = run_functional_validation(
        analysis=_analysis(),
        artifacts=artifacts,
        timeout_seconds=5,
        command_runner=fake_runner,
    )

    assert report.passed is False
    assert report.steps[0].status == "failed"
    assert report.steps[0].failure_category == "timeout"


def test_functional_validation_marks_missing_prereq_for_non_command_step(tmp_path: Path) -> None:
    analysis = AnalyzerIR.from_dict(
        {
            "software": "demo",
            "interface": "python_sdk",
            "version": "1.0",
            "setup": {
                "install": "",
                "auth": "No auth",
                "env_vars": [],
                "prerequisites": [],
            },
            "capability_groups": [],
            "workflows": [
                {
                    "name": "Run smoke",
                    "steps": ["Initialize SDK client and verify state"],
                    "common_errors": [],
                }
            ],
            "gotchas": ["x", "y", "z", "a", "b"],
            "analysis_sources": ["python_sdk:pypi:demo"],
        }
    )
    artifacts = GeneratedArtifacts(
        skill_path=tmp_path / "SKILL.md",
        reference_paths={},
        token_counts={},
        line_counts={},
        script_paths={},
    )

    report = run_functional_validation(
        analysis=analysis,
        artifacts=artifacts,
        timeout_seconds=5,
    )

    names = [step.name for step in report.steps]
    assert names == ["setup_install", "verify_setup_script", "workflow_first_step"]
    assert report.steps[0].status == "skipped"
    assert report.steps[0].failure_category == "missing_prereq"
    assert report.steps[2].status == "skipped"
    assert report.steps[2].failure_category == "missing_prereq"


def test_functional_validation_marks_unsupported_command_as_missing_prereq(tmp_path: Path) -> None:
    def fake_runner(command: str, *, timeout_seconds: int):  # noqa: ARG001
        return 127, "", "/bin/sh: madeup-command: command not found"

    artifacts = GeneratedArtifacts(
        skill_path=tmp_path / "SKILL.md",
        reference_paths={},
        token_counts={},
        line_counts={},
        script_paths={},
    )

    analysis = AnalyzerIR.from_dict(
        {
            "software": "demo",
            "interface": "python_sdk",
            "version": "1.0",
            "setup": {
                "install": "madeup-command install demo",
                "auth": "none",
                "env_vars": [],
                "prerequisites": [],
            },
            "capability_groups": [],
            "workflows": [],
            "gotchas": [],
            "analysis_sources": ["python_sdk:pypi:demo"],
        }
    )

    report = run_functional_validation(
        analysis=analysis,
        artifacts=artifacts,
        timeout_seconds=5,
        command_runner=fake_runner,
    )

    assert report.passed is False
    assert report.steps[0].status == "failed"
    assert report.steps[0].failure_category == "missing_prereq"


def test_functional_validation_truncates_long_output_excerpts(tmp_path: Path) -> None:
    long_stdout = "x" * 2000
    long_stderr = "y" * 2000

    def fake_runner(command: str, *, timeout_seconds: int):  # noqa: ARG001
        return 1, long_stdout, long_stderr

    artifacts = GeneratedArtifacts(
        skill_path=tmp_path / "SKILL.md",
        reference_paths={},
        token_counts={},
        line_counts={},
        script_paths={},
    )

    report = run_functional_validation(
        analysis=_analysis(),
        artifacts=artifacts,
        timeout_seconds=5,
        command_runner=fake_runner,
    )

    first_step = report.steps[0]
    assert first_step.status == "failed"
    assert first_step.failure_category == "command_failed"
    assert len(first_step.stdout_excerpt) < 800
    assert first_step.stdout_excerpt.endswith("...")
    assert len(first_step.stderr_excerpt) < 800
    assert first_step.stderr_excerpt.endswith("...")


@pytest.mark.security
def test_functional_validation_skips_unsafe_workflow_command(tmp_path: Path) -> None:
    analysis = AnalyzerIR.from_dict(
        {
            "software": "demo",
            "interface": "python_sdk",
            "version": "1.0",
            "setup": {
                "install": "",
                "auth": "none",
                "env_vars": [],
                "prerequisites": [],
            },
            "capability_groups": [],
            "workflows": [
                {
                    "name": "Unsafe",
                    "steps": ["`python -c \"print(1)\"; rm -rf /`"],
                    "common_errors": [],
                }
            ],
            "gotchas": [],
            "analysis_sources": ["python_sdk:pypi:demo"],
        }
    )
    artifacts = GeneratedArtifacts(
        skill_path=tmp_path / "SKILL.md",
        reference_paths={},
        token_counts={},
        line_counts={},
        script_paths={},
    )

    report = run_functional_validation(
        analysis=analysis,
        artifacts=artifacts,
        timeout_seconds=5,
    )

    workflow_step = next(step for step in report.steps if step.name == "workflow_first_step")
    assert workflow_step.status == "skipped"
    assert workflow_step.failure_category == "missing_prereq"


@pytest.mark.security
def test_functional_validation_redacts_secret_like_values(tmp_path: Path) -> None:
    def fake_runner(command: str, *, timeout_seconds: int):  # noqa: ARG001
        return (
            1,
            "Authorization: Bearer abcdefghijklmnop",
            "OPENAI_API_KEY=sk-12345678901234567890",
        )

    artifacts = GeneratedArtifacts(
        skill_path=tmp_path / "SKILL.md",
        reference_paths={},
        token_counts={},
        line_counts={},
        script_paths={},
    )

    report = run_functional_validation(
        analysis=_analysis(),
        artifacts=artifacts,
        timeout_seconds=5,
        command_runner=fake_runner,
    )

    first_step = report.steps[0]
    assert "Bearer [REDACTED]" in first_step.stdout_excerpt
    assert "OPENAI_API_KEY=[REDACTED]" in first_step.stderr_excerpt
    assert "1234567890" not in first_step.stderr_excerpt
