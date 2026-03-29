from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from use_anything.cli import cli


def test_cli_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "use-anything" in result.output
    assert "run" in result.output
    assert "use-anything run requests" in result.output


def test_cli_requires_target_when_no_subcommand() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, [])

    assert result.exit_code != 0
    assert "TARGET is required" in result.output
    assert "use-anything run requests" in result.output


def test_cli_routes_unknown_first_token_to_default_run(monkeypatch) -> None:
    runner = CliRunner()
    calls: dict[str, object] = {}

    class FakePipeline:
        def run(self, **kwargs):  # noqa: ANN003
            calls.update(kwargs)
            from use_anything.models import InterfaceCandidate, PipelineResult, ProbeResult, RankedInterface, RankResult

            probe_result = ProbeResult(
                target=kwargs["target"],
                target_type="pypi_package",
                interfaces_found=[
                    InterfaceCandidate(
                        type="python_sdk",
                        location=f"pypi:{kwargs['target']}",
                        quality_score=0.9,
                        coverage="full",
                        notes="sdk",
                    )
                ],
            )
            rank_result = RankResult(
                primary=RankedInterface(type="python_sdk", score=0.9, reasoning="best"),
                secondary=None,
                rejected=[],
            )
            return PipelineResult(
                probe_result=probe_result,
                rank_result=rank_result,
                probe_only=True,
            )

    monkeypatch.setattr("use_anything.cli.UseAnythingPipeline", FakePipeline)

    result = runner.invoke(cli, ["requests", "--probe-only"])

    assert result.exit_code == 0
    assert calls["target"] == "requests"


def test_cli_run_subcommand_uses_pipeline(monkeypatch) -> None:
    runner = CliRunner()
    calls: dict[str, object] = {}

    class FakePipeline:
        def run(self, **kwargs):  # noqa: ANN003
            calls.update(kwargs)
            from use_anything.models import InterfaceCandidate, PipelineResult, ProbeResult, RankedInterface, RankResult

            probe_result = ProbeResult(
                target=kwargs["target"],
                target_type="pypi_package",
                interfaces_found=[
                    InterfaceCandidate(
                        type="python_sdk",
                        location=f"pypi:{kwargs['target']}",
                        quality_score=0.9,
                        coverage="full",
                        notes="sdk",
                    )
                ],
            )
            rank_result = RankResult(
                primary=RankedInterface(type="python_sdk", score=0.9, reasoning="best"),
                secondary=None,
                rejected=[],
            )
            return PipelineResult(
                probe_result=probe_result,
                rank_result=rank_result,
                probe_only=True,
            )

    monkeypatch.setattr("use_anything.cli.UseAnythingPipeline", FakePipeline)

    result = runner.invoke(cli, ["run", "requests", "--probe-only"])

    assert result.exit_code == 0
    assert calls["target"] == "requests"


def test_cli_short_help_flag_is_not_routed_as_target() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["-h"])

    assert result.exit_code == 0
    assert "Generate agent skills from software interfaces" in result.output


def test_cli_probe_subcommand(monkeypatch) -> None:
    runner = CliRunner()

    class FakeProber:
        def probe_target(self, target: str | None, *, binary_name: str | None = None):
            from use_anything.models import ProbeResult

            return ProbeResult(
                target=target,
                target_type="pypi_package",
                interfaces_found=[],
                recommended_interface="python_sdk",
                reasoning="test",
            )

    monkeypatch.setattr("use_anything.cli.Prober", FakeProber)

    result = runner.invoke(cli, ["probe", "requests"])

    assert result.exit_code == 0
    assert '"target": "requests"' in result.output


def test_cli_rejects_target_and_binary_together() -> None:
    runner = CliRunner()

    result = runner.invoke(cli, ["requests", "--binary", "ffmpeg", "--probe-only"])

    assert result.exit_code != 0
    assert "Provide only one target source" in result.output


def test_cli_accepts_binary_without_target(monkeypatch) -> None:
    runner = CliRunner()
    calls: dict[str, str | None] = {}

    class FakePipeline:
        def run(self, **kwargs):  # noqa: ANN003
            calls.update(kwargs)
            from use_anything.models import InterfaceCandidate, ProbeResult, RankedInterface, RankResult

            probe_result = ProbeResult(
                target="ffmpeg",
                target_type="binary",
                interfaces_found=[
                    InterfaceCandidate(
                        type="cli_tool",
                        location="binary:ffmpeg",
                        quality_score=0.7,
                        coverage="partial",
                        notes="binary help output",
                    )
                ],
            )
            rank_result = RankResult(
                primary=RankedInterface(type="cli_tool", score=0.7, reasoning="test"),
                secondary=None,
                rejected=[],
            )
            from use_anything.models import PipelineResult

            return PipelineResult(
                probe_result=probe_result,
                rank_result=rank_result,
                probe_only=True,
            )

    monkeypatch.setattr("use_anything.cli.UseAnythingPipeline", FakePipeline)

    result = runner.invoke(cli, ["--binary", "ffmpeg", "--probe-only"])

    assert result.exit_code == 0
    assert calls["target"] is None
    assert calls["binary_name"] == "ffmpeg"


def test_cli_summary_includes_analysis_sources(monkeypatch, tmp_path: Path) -> None:
    runner = CliRunner()

    class FakePipeline:
        def run(self, **kwargs):  # noqa: ANN003
            from use_anything.models import (
                AnalyzerIR,
                GeneratedArtifacts,
                InterfaceCandidate,
                PipelineResult,
                ProbeResult,
                RankedInterface,
                RankResult,
                ValidationReport,
            )

            probe_result = ProbeResult(
                target="requests",
                target_type="pypi_package",
                interfaces_found=[
                    InterfaceCandidate(
                        type="python_sdk",
                        location="pypi:requests",
                        quality_score=0.95,
                        coverage="full",
                        notes="sdk",
                    )
                ],
            )
            rank_result = RankResult(
                primary=RankedInterface(type="python_sdk", score=0.95, reasoning="best"),
                secondary=None,
                rejected=[],
            )
            analysis = AnalyzerIR.from_dict(
                {
                    "software": "requests",
                    "interface": "python_sdk",
                    "version": "2.32.3",
                    "setup": {
                        "install": "pip install requests",
                        "auth": "none",
                        "env_vars": [],
                        "prerequisites": [],
                    },
                    "capability_groups": [],
                    "workflows": [],
                    "gotchas": [],
                    "analysis_sources": ["python_sdk:pypi:requests"],
                }
            )

            return PipelineResult(
                probe_result=probe_result,
                rank_result=rank_result,
                analysis=analysis,
                artifacts=GeneratedArtifacts(
                    skill_path=tmp_path / "SKILL.md",
                    reference_paths={},
                    token_counts={},
                    line_counts={},
                ),
                validation_report=ValidationReport(passed=True, errors=[], warnings=[], metrics={}),
                probe_only=False,
            )

    monkeypatch.setattr("use_anything.cli.UseAnythingPipeline", FakePipeline)

    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text(
        "# requests\n\n## Core workflows\n\n### one\n\n1. step\n\n### two\n\n1. step\n\n### three\n\n1. step\n"
    )

    result = runner.invoke(cli, ["requests"])

    assert result.exit_code == 0
    assert '"analysis_sources"' in result.output
    assert '"analysis_workflow_count"' in result.output
    assert '"emitted_workflow_count"' in result.output


def test_cli_summary_uses_emitted_workflow_count_when_available(monkeypatch, tmp_path: Path) -> None:
    runner = CliRunner()

    class FakePipeline:
        def run(self, **kwargs):  # noqa: ANN003
            from use_anything.models import (
                AnalyzerIR,
                GeneratedArtifacts,
                InterfaceCandidate,
                PipelineResult,
                ProbeResult,
                RankedInterface,
                RankResult,
                ValidationReport,
            )

            probe_result = ProbeResult(
                target="requests",
                target_type="pypi_package",
                interfaces_found=[
                    InterfaceCandidate(
                        type="python_sdk",
                        location="pypi:requests",
                        quality_score=0.95,
                        coverage="full",
                        notes="sdk",
                    )
                ],
            )
            rank_result = RankResult(
                primary=RankedInterface(type="python_sdk", score=0.95, reasoning="best"),
                secondary=None,
                rejected=[],
            )
            analysis = AnalyzerIR.from_dict(
                {
                    "software": "requests",
                    "interface": "python_sdk",
                    "version": "2.32.3",
                    "setup": {
                        "install": "pip install requests",
                        "auth": "none",
                        "env_vars": [],
                        "prerequisites": [],
                    },
                    "capability_groups": [],
                    "workflows": [
                        {
                            "name": "single",
                            "steps": ["1. one"],
                            "common_errors": [],
                        }
                    ],
                    "gotchas": [],
                    "analysis_sources": ["python_sdk:pypi:requests"],
                }
            )
            skill_path = tmp_path / "SKILL.md"
            skill_path.write_text(
                "# requests\n\n## Core workflows\n\n### one\n\n1. step\n\n### two\n\n1. step\n\n### three\n\n1. step\n"
            )
            return PipelineResult(
                probe_result=probe_result,
                rank_result=rank_result,
                analysis=analysis,
                artifacts=GeneratedArtifacts(
                    skill_path=skill_path,
                    reference_paths={},
                    token_counts={},
                    line_counts={},
                ),
                validation_report=ValidationReport(passed=True, errors=[], warnings=[], metrics={}),
                probe_only=False,
            )

    monkeypatch.setattr("use_anything.cli.UseAnythingPipeline", FakePipeline)

    result = runner.invoke(cli, ["requests"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["analysis_workflow_count"] == 1
    assert payload["emitted_workflow_count"] == 3
    assert payload["workflow_count"] == 3


def test_cli_passes_force_flag_to_pipeline(monkeypatch) -> None:
    runner = CliRunner()
    calls: dict[str, object] = {}

    class FakePipeline:
        def run(self, **kwargs):  # noqa: ANN003
            calls.update(kwargs)
            from use_anything.models import InterfaceCandidate, PipelineResult, ProbeResult, RankedInterface, RankResult

            probe_result = ProbeResult(
                target="requests",
                target_type="pypi_package",
                interfaces_found=[
                    InterfaceCandidate(
                        type="python_sdk",
                        location="pypi:requests",
                        quality_score=0.95,
                        coverage="full",
                        notes="sdk",
                    )
                ],
            )
            rank_result = RankResult(
                primary=RankedInterface(type="python_sdk", score=0.95, reasoning="best"),
                secondary=None,
                rejected=[],
            )
            return PipelineResult(
                probe_result=probe_result,
                rank_result=rank_result,
                probe_only=True,
            )

    monkeypatch.setattr("use_anything.cli.UseAnythingPipeline", FakePipeline)

    result = runner.invoke(cli, ["requests", "--probe-only", "--force"])

    assert result.exit_code == 0
    assert calls["force"] is True


def test_cli_passes_analysis_limit_options_to_pipeline(monkeypatch) -> None:
    runner = CliRunner()
    calls: dict[str, object] = {}

    class FakePipeline:
        def run(self, **kwargs):  # noqa: ANN003
            calls.update(kwargs)
            from use_anything.models import InterfaceCandidate, PipelineResult, ProbeResult, RankedInterface, RankResult

            probe_result = ProbeResult(
                target="requests",
                target_type="pypi_package",
                interfaces_found=[
                    InterfaceCandidate(
                        type="python_sdk",
                        location="pypi:requests",
                        quality_score=0.95,
                        coverage="full",
                        notes="sdk",
                    )
                ],
            )
            rank_result = RankResult(
                primary=RankedInterface(type="python_sdk", score=0.95, reasoning="best"),
                secondary=None,
                rejected=[],
            )
            return PipelineResult(
                probe_result=probe_result,
                rank_result=rank_result,
                probe_only=True,
            )

    monkeypatch.setattr("use_anything.cli.UseAnythingPipeline", FakePipeline)

    result = runner.invoke(
        cli,
        [
            "requests",
            "--probe-only",
            "--analysis-timeout-seconds",
            "700",
            "--analysis-max-retries",
            "3",
        ],
    )

    assert result.exit_code == 0
    assert calls["analysis_timeout_seconds"] == 700
    assert calls["analysis_max_retries"] == 3


def test_cli_passes_functional_options_to_pipeline(monkeypatch) -> None:
    runner = CliRunner()
    calls: dict[str, object] = {}

    class FakePipeline:
        def run(self, **kwargs):  # noqa: ANN003
            calls.update(kwargs)
            from use_anything.models import InterfaceCandidate, PipelineResult, ProbeResult, RankedInterface, RankResult

            probe_result = ProbeResult(
                target="requests",
                target_type="pypi_package",
                interfaces_found=[
                    InterfaceCandidate(
                        type="python_sdk",
                        location="pypi:requests",
                        quality_score=0.95,
                        coverage="full",
                        notes="sdk",
                    )
                ],
            )
            rank_result = RankResult(
                primary=RankedInterface(type="python_sdk", score=0.95, reasoning="best"),
                secondary=None,
                rejected=[],
            )
            return PipelineResult(
                probe_result=probe_result,
                rank_result=rank_result,
                probe_only=True,
            )

    monkeypatch.setattr("use_anything.cli.UseAnythingPipeline", FakePipeline)

    result = runner.invoke(
        cli,
        [
            "requests",
            "--probe-only",
            "--functional-checks",
            "--functional-timeout-seconds",
            "88",
        ],
    )

    assert result.exit_code == 0
    assert calls["functional_checks"] is True
    assert calls["functional_timeout_seconds"] == 88


def test_cli_summary_includes_functional_validation(monkeypatch, tmp_path: Path) -> None:
    runner = CliRunner()

    class FakePipeline:
        def run(self, **kwargs):  # noqa: ANN003
            from use_anything.models import (
                AnalyzerIR,
                FunctionalCheckStepReport,
                FunctionalValidationReport,
                GeneratedArtifacts,
                InterfaceCandidate,
                PipelineResult,
                ProbeResult,
                RankedInterface,
                RankResult,
                ValidationReport,
            )

            probe_result = ProbeResult(
                target="requests",
                target_type="pypi_package",
                interfaces_found=[
                    InterfaceCandidate(
                        type="python_sdk",
                        location="pypi:requests",
                        quality_score=0.95,
                        coverage="full",
                        notes="sdk",
                    )
                ],
            )
            rank_result = RankResult(
                primary=RankedInterface(type="python_sdk", score=0.95, reasoning="best"),
                secondary=None,
                rejected=[],
            )
            analysis = AnalyzerIR.from_dict(
                {
                    "software": "requests",
                    "interface": "python_sdk",
                    "version": "2.32.3",
                    "setup": {
                        "install": "pip install requests",
                        "auth": "none",
                        "env_vars": [],
                        "prerequisites": [],
                    },
                    "capability_groups": [],
                    "workflows": [],
                    "gotchas": [],
                    "analysis_sources": ["python_sdk:pypi:requests"],
                    "gotcha_provenance": [],
                }
            )

            skill_path = tmp_path / "SKILL.md"
            skill_path.write_text("# requests\n")

            return PipelineResult(
                probe_result=probe_result,
                rank_result=rank_result,
                analysis=analysis,
                artifacts=GeneratedArtifacts(
                    skill_path=skill_path,
                    reference_paths={},
                    token_counts={},
                    line_counts={},
                ),
                validation_report=ValidationReport(passed=True, errors=[], warnings=[], metrics={}),
                functional_validation=FunctionalValidationReport(
                    enabled=True,
                    passed=True,
                    steps=[
                        FunctionalCheckStepReport(
                            name="setup_install",
                            command="pip install requests",
                            status="passed",
                            failure_category=None,
                            duration_ms=11,
                            stdout_excerpt="ok",
                            stderr_excerpt="",
                        )
                    ],
                    warnings=[],
                ),
                probe_only=False,
            )

    monkeypatch.setattr("use_anything.cli.UseAnythingPipeline", FakePipeline)

    result = runner.invoke(cli, ["requests", "--functional-checks"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["functional_checks_enabled"] is True
    assert payload["functional_validation"]["enabled"] is True
    assert payload["functional_validation"]["steps"][0]["name"] == "setup_install"


def test_cli_summary_reports_null_functional_validation_when_disabled(monkeypatch, tmp_path: Path) -> None:
    runner = CliRunner()

    class FakePipeline:
        def run(self, **kwargs):  # noqa: ANN003
            from use_anything.models import (
                AnalyzerIR,
                GeneratedArtifacts,
                InterfaceCandidate,
                PipelineResult,
                ProbeResult,
                RankedInterface,
                RankResult,
                ValidationReport,
            )

            probe_result = ProbeResult(
                target="requests",
                target_type="pypi_package",
                interfaces_found=[
                    InterfaceCandidate(
                        type="python_sdk",
                        location="pypi:requests",
                        quality_score=0.95,
                        coverage="full",
                        notes="sdk",
                    )
                ],
            )
            rank_result = RankResult(
                primary=RankedInterface(type="python_sdk", score=0.95, reasoning="best"),
                secondary=None,
                rejected=[],
            )
            analysis = AnalyzerIR.from_dict(
                {
                    "software": "requests",
                    "interface": "python_sdk",
                    "version": "2.32.3",
                    "setup": {
                        "install": "pip install requests",
                        "auth": "none",
                        "env_vars": [],
                        "prerequisites": [],
                    },
                    "capability_groups": [],
                    "workflows": [],
                    "gotchas": [],
                    "analysis_sources": ["python_sdk:pypi:requests"],
                }
            )
            return PipelineResult(
                probe_result=probe_result,
                rank_result=rank_result,
                analysis=analysis,
                artifacts=GeneratedArtifacts(
                    skill_path=tmp_path / "SKILL.md",
                    reference_paths={},
                    token_counts={},
                    line_counts={},
                ),
                validation_report=ValidationReport(passed=True, errors=[], warnings=[], metrics={}),
                functional_validation=None,
                probe_only=False,
            )

    monkeypatch.setattr("use_anything.cli.UseAnythingPipeline", FakePipeline)
    result = runner.invoke(cli, ["requests"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["functional_checks_enabled"] is False
    assert payload["functional_validation"] is None
