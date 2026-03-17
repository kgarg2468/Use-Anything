from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from use_anything.cli import cli


def test_cli_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "use-anything" in result.output


def test_cli_requires_target_when_no_subcommand() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, [])

    assert result.exit_code != 0
    assert "TARGET is required" in result.output


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

    result = runner.invoke(cli, ["requests"])

    assert result.exit_code == 0
    assert '"analysis_sources"' in result.output
