"""End-to-end orchestrator for Use-Anything."""

from __future__ import annotations

from pathlib import Path

from use_anything.analyze.analyzer import Analyzer
from use_anything.exceptions import UnsupportedTargetError
from use_anything.generate.generator import Generator
from use_anything.models import PipelineResult, RankedInterface
from use_anything.probe.prober import Prober
from use_anything.rank.ranker import Ranker
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

        analyzer = self.analyzer or Analyzer(model=model)
        analysis = analyzer.analyze(probe_result=probe_result, rank_result=rank_result)

        target_output = Path(output_dir) if output_dir else Path.cwd() / f"use-anything-{probe_result.target}"
        artifacts = self.generator.generate(
            analysis,
            target_output,
            source_interface=rank_result.primary.type,
        )
        validation_report = self.validator.validate_directory(target_output)

        return PipelineResult(
            probe_result=probe_result,
            rank_result=rank_result,
            analysis=analysis,
            artifacts=artifacts,
            validation_report=validation_report,
            probe_only=False,
        )
