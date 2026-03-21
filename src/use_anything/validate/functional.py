"""Optional runtime functional validation for generated skills."""

from __future__ import annotations

import re
import subprocess
import time
from collections.abc import Callable

from use_anything.models import AnalyzerIR, FunctionalCheckStepReport, FunctionalValidationReport, GeneratedArtifacts

COMMAND_PREFIXES = (
    "python ",
    "pip ",
    "uv ",
    "pytest ",
    "curl ",
    "npm ",
    "node ",
    "bash ",
    "sh ",
    "ffmpeg ",
    "ffprobe ",
    "git ",
)
MAX_OUTPUT_EXCERPT_CHARS = 700
MISSING_COMMAND_PATTERNS = (
    "command not found",
    "not recognized as an internal or external command",
    "no such file or directory",
)
DANGEROUS_COMMAND_FRAGMENTS = (
    "&&",
    "||",
    ";",
    "|",
    "$(",
    "`",
    "\n",
    "\r",
)

def run_functional_validation(
    *,
    analysis: AnalyzerIR,
    artifacts: GeneratedArtifacts,
    timeout_seconds: int,
    command_runner: Callable[[str, int], tuple[int, str, str]] | None = None,
) -> FunctionalValidationReport:
    """Run optional install/auth/workflow smoke checks and return a structured report."""

    runner = command_runner or _run_command
    steps: list[FunctionalCheckStepReport] = []

    install_command = analysis.setup.install.strip()
    steps.append(
        _execute_step(
            name="setup_install",
            command=install_command,
            timeout_seconds=timeout_seconds,
            runner=runner,
        )
    )

    verify_setup_path = artifacts.script_paths.get("verify_setup") if artifacts.script_paths else None
    verify_command = f'python "{verify_setup_path}"' if verify_setup_path and verify_setup_path.exists() else ""
    steps.append(
        _execute_step(
            name="verify_setup_script",
            command=verify_command,
            timeout_seconds=timeout_seconds,
            runner=runner,
        )
    )

    workflow_step_command = _extract_first_workflow_command(analysis)
    steps.append(
        _execute_step(
            name="workflow_first_step",
            command=workflow_step_command,
            timeout_seconds=timeout_seconds,
            runner=runner,
        )
    )

    passed = all(step.status != "failed" for step in steps)
    warnings = [
        f"Functional check skipped ({step.name}): {step.failure_category}"
        for step in steps
        if step.status == "skipped"
    ]
    return FunctionalValidationReport(enabled=True, passed=passed, steps=steps, warnings=warnings)


def _execute_step(
    *,
    name: str,
    command: str,
    timeout_seconds: int,
    runner: Callable[[str, int], tuple[int, str, str]],
) -> FunctionalCheckStepReport:
    command_text = command.strip()
    if not command_text:
        return FunctionalCheckStepReport(
            name=name,
            command="",
            status="skipped",
            failure_category="missing_prereq",
            duration_ms=0,
            stdout_excerpt="",
            stderr_excerpt="Command unavailable for this check",
        )

    start = time.perf_counter()
    try:
        return_code, stdout, stderr = runner(command_text, timeout_seconds=timeout_seconds)
    except subprocess.TimeoutExpired:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return FunctionalCheckStepReport(
            name=name,
            command=command_text,
            status="failed",
            failure_category="timeout",
            duration_ms=elapsed_ms,
            stdout_excerpt="",
            stderr_excerpt=f"Command timed out after {timeout_seconds} seconds",
        )
    except Exception as exc:  # noqa: BLE001
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return FunctionalCheckStepReport(
            name=name,
            command=command_text,
            status="failed",
            failure_category="command_failed",
            duration_ms=elapsed_ms,
            stdout_excerpt="",
            stderr_excerpt=_truncate(_redact_sensitive(str(exc))),
        )

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    status = "passed" if return_code == 0 else "failed"
    failure_category = None
    if return_code != 0:
        failure_category = _classify_failed_command(return_code=return_code, stderr=stderr)
    return FunctionalCheckStepReport(
        name=name,
        command=command_text,
        status=status,
        failure_category=failure_category,
        duration_ms=elapsed_ms,
        stdout_excerpt=_truncate(_redact_sensitive(stdout)),
        stderr_excerpt=_truncate(_redact_sensitive(stderr)),
    )


def _extract_first_workflow_command(analysis: AnalyzerIR) -> str:
    if not analysis.workflows:
        return ""
    first_workflow = analysis.workflows[0]
    if not first_workflow.steps:
        return ""

    step = _strip_numbering(first_workflow.steps[0])
    code_match = re.search(r"`([^`]+)`", step)
    if code_match:
        command = code_match.group(1).strip()
        return command if _is_safe_command(command) else ""

    lowered = step.lower().strip()
    if lowered.startswith(COMMAND_PREFIXES):
        command = step.strip()
        return command if _is_safe_command(command) else ""
    return ""


def _strip_numbering(step: str) -> str:
    return re.sub(r"^\s*\d+[.)]?\s*", "", step).strip()


def _truncate(value: str) -> str:
    text = (value or "").strip()
    if len(text) <= MAX_OUTPUT_EXCERPT_CHARS:
        return text
    return f"{text[:MAX_OUTPUT_EXCERPT_CHARS]}..."


def _run_command(command: str, timeout_seconds: int) -> tuple[int, str, str]:
    completed = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout_seconds,
    )
    return completed.returncode, completed.stdout or "", completed.stderr or ""


def _classify_failed_command(*, return_code: int, stderr: str) -> str:
    stderr_lower = (stderr or "").lower()
    if return_code == 127:
        return "missing_prereq"
    if any(pattern in stderr_lower for pattern in MISSING_COMMAND_PATTERNS):
        return "missing_prereq"
    return "command_failed"


def _is_safe_command(command: str) -> bool:
    stripped = command.strip()
    if not stripped:
        return False
    return not any(fragment in stripped for fragment in DANGEROUS_COMMAND_FRAGMENTS)


def _redact_sensitive(value: str) -> str:
    if not value:
        return ""

    redacted = value
    redacted = re.sub(
        r"([A-Z0-9_]*(?:TOKEN|KEY|SECRET|PASSWORD)[A-Z0-9_]*\s*=\s*)([^\s\"']+)",
        r"\1[REDACTED]",
        redacted,
        flags=re.IGNORECASE,
    )
    redacted = re.sub(r"Bearer\s+[A-Za-z0-9._-]+", "Bearer [REDACTED]", redacted, flags=re.IGNORECASE)
    redacted = re.sub(r"\bsk-[A-Za-z0-9]{10,}\b", "sk-[REDACTED]", redacted)
    return redacted
