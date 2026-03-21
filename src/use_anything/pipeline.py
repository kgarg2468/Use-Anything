"""End-to-end orchestrator for Use-Anything."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import httpx

from use_anything.analyze.analyzer import Analyzer
from use_anything.exceptions import UnsupportedTargetError
from use_anything.generate.generator import Generator
from use_anything.models import (
    FunctionalCheckStepReport,
    FunctionalValidationReport,
    InterfaceCandidate,
    PipelineResult,
    RankedInterface,
)
from use_anything.probe.prober import Prober
from use_anything.rank.ranker import Ranker
from use_anything.validate.functional import run_functional_validation
from use_anything.validate.validator import Validator

SUPPORTED_INTERFACE_TYPES = {
    "openapi_spec",
    "rest_api_docs",
    "python_sdk",
    "node_sdk",
    "cli_tool",
    "graphql_api",
    "grpc_api",
    "file_format",
    "plugin_api",
    "llms_txt",
    "existing_skill",
}
CODEX_CLI_MODEL = "codex-cli"
DEFAULT_CODEX_ANALYSIS_TIMEOUT_SECONDS = 600
DEFAULT_CODEX_ANALYSIS_MAX_RETRIES = 1
DEFAULT_FUNCTIONAL_TIMEOUT_SECONDS = 30


class UseAnythingPipeline:
    """Coordinates probe, rank, analyze, generate, and validate phases."""

    def __init__(
        self,
        *,
        prober: Prober | None = None,
        ranker: Ranker | None = None,
        analyzer: Analyzer | None = None,
        generator: Generator | None = None,
        validator: Validator | None = None,
    ) -> None:
        self.prober = prober or Prober()
        self.ranker = ranker or Ranker()
        self.analyzer = analyzer
        self.generator = generator or Generator()
        self.validator = validator or Validator()

    def run(
        self,
        *,
        target: str | None,
        binary_name: str | None = None,
        model: str | None = None,
        forced_interface: str | None = None,
        output_dir: Path | str | None = None,
        probe_only: bool = False,
        force: bool = False,
        analysis_timeout_seconds: int | None = None,
        analysis_max_retries: int | None = None,
        functional_checks: bool = False,
        functional_timeout_seconds: int | None = None,
    ) -> PipelineResult:
        probe_result = self.prober.probe_target(target, binary_name=binary_name)
        rank_result = self.ranker.rank(probe_result)

        if forced_interface:
            if forced_interface not in SUPPORTED_INTERFACE_TYPES:
                raise UnsupportedTargetError(f"Unsupported forced interface '{forced_interface}'")

            discovered_types = {candidate.type for candidate in probe_result.interfaces_found}
            if forced_interface not in discovered_types:
                discovered_text = ", ".join(sorted(discovered_types)) or "none"
                raise UnsupportedTargetError(
                    f"Forced interface '{forced_interface}' was not discovered for this target. "
                    f"Discovered interfaces: {discovered_text}"
                )

            rank_result.primary = RankedInterface(
                type=forced_interface,
                score=1.0,
                reasoning="Interface forced via CLI flag",
            )

        if probe_only:
            return PipelineResult(
                probe_result=probe_result,
                rank_result=rank_result,
                probe_only=True,
            )

        normalized_model = (model or "").strip().lower()
        resolved_timeout_seconds = analysis_timeout_seconds
        resolved_max_retries = analysis_max_retries
        if normalized_model == CODEX_CLI_MODEL:
            if resolved_timeout_seconds is None:
                resolved_timeout_seconds = DEFAULT_CODEX_ANALYSIS_TIMEOUT_SECONDS
            if resolved_max_retries is None:
                resolved_max_retries = DEFAULT_CODEX_ANALYSIS_MAX_RETRIES

        analyzer = self.analyzer or Analyzer(
            model=model,
            timeout_seconds=resolved_timeout_seconds,
            max_retries=resolved_max_retries,
        )
        analysis = analyzer.analyze(probe_result=probe_result, rank_result=rank_result)

        target_output = (
            Path(output_dir) if output_dir else Path.cwd() / f"use-anything-{_default_output_slug(probe_result.target)}"
        )
        existing_skill = None if force else self._load_existing_skill_content(probe_result.interfaces_found)
        artifacts = self.generator.generate(
            analysis,
            target_output,
            source_interface=rank_result.primary.type,
            existing_skill=existing_skill,
            force=force,
        )
        functional_validation = None
        if functional_checks:
            try:
                functional_validation = run_functional_validation(
                    analysis=analysis,
                    artifacts=artifacts,
                    timeout_seconds=functional_timeout_seconds or DEFAULT_FUNCTIONAL_TIMEOUT_SECONDS,
                )
            except Exception as exc:  # noqa: BLE001
                functional_validation = _functional_validation_runner_failure(exc)
        validation_report = self.validator.validate_directory(target_output)

        return PipelineResult(
            probe_result=probe_result,
            rank_result=rank_result,
            analysis=analysis,
            artifacts=artifacts,
            validation_report=validation_report,
            functional_validation=functional_validation,
            probe_only=False,
        )

    def _load_existing_skill_content(self, candidates: list[InterfaceCandidate]) -> str | None:
        existing_candidates = [candidate for candidate in candidates if candidate.type == "existing_skill"]
        if not existing_candidates:
            return None

        location = existing_candidates[0].location
        path = Path(location)
        if path.exists() and path.is_file():
            return path.read_text(encoding="utf-8")

        if location.startswith("http://") or location.startswith("https://"):
            try:
                response = httpx.get(location, timeout=15.0)
                response.raise_for_status()
                return response.text
            except httpx.HTTPError:
                return None

        return None


def _default_output_slug(target: str) -> str:
    value = (target or "").strip().lower()
    parsed = urlparse(value)
    if parsed.scheme and parsed.netloc:
        value = f"{parsed.netloc}{parsed.path}".strip("/")
    value = value.replace("\\", "/").replace("/", "-")
    value = re.sub(r"[^a-z0-9._-]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-._")
    return value or "target"


def _functional_validation_runner_failure(exc: Exception) -> FunctionalValidationReport:
    message = f"functional validation runner crashed: {exc}"
    return FunctionalValidationReport(
        enabled=True,
        passed=False,
        steps=[
            FunctionalCheckStepReport(
                name="functional_validation",
                command="",
                status="failed",
                failure_category="command_failed",
                duration_ms=0,
                stdout_excerpt="",
                stderr_excerpt=message[:700],
            )
        ],
        warnings=["Functional validation crashed; pipeline continued with failed functional report."],
    )
