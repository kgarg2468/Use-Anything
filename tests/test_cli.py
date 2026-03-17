from __future__ import annotations

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
        def probe_target(self, target: str):
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
