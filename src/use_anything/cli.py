"""Click CLI entrypoint."""

from __future__ import annotations

import json
from pathlib import Path

import click

from use_anything.exceptions import AnalyzeError, ProbeError, UnsupportedTargetError
from use_anything.pipeline import UseAnythingPipeline
from use_anything.probe.prober import Prober
from use_anything.probe.targets import classify_target
from use_anything.rank.ranker import Ranker
from use_anything.validate.validator import Validator

CONTEXT_SETTINGS = {
    "help_option_names": ["-h", "--help"],
}
HELP_EPILOG = """Examples:
  use-anything run requests
  use-anything requests --probe-only
  use-anything probe requests
"""


class TargetAwareGroup(click.Group):
    """Route unknown first tokens to a hidden default run command."""

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        if args and args[0] not in self.commands:
            if args[0] in CONTEXT_SETTINGS["help_option_names"]:
                return super().parse_args(ctx, args)
            args = ["run", *args]
        return super().parse_args(ctx, args)


@click.group(
    name="use-anything",
    cls=TargetAwareGroup,
    context_settings=CONTEXT_SETTINGS,
    invoke_without_command=True,
    epilog=HELP_EPILOG,
)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Generate agent skills from software interfaces."""

    if ctx.invoked_subcommand is None:
        raise click.UsageError("TARGET is required when no subcommand is provided\n\n" + HELP_EPILOG)


@cli.command("run")
@cli.command(name="_run", hidden=True)
@click.argument("target", required=False)
@click.option("--binary", "binary_name", help="Probe a binary available on PATH")
@click.option("--model", help="LLM model override for analysis and generation")
@click.option("--interface", "forced_interface", help="Force a specific interface type")
@click.option("-o", "--output-dir", type=click.Path(path_type=Path), help="Output directory")
@click.option("--probe-only", is_flag=True, help="Run only probe and rank phases")
@click.option("--force", is_flag=True, help="Bypass enhancement merge and regenerate canonical output")
@click.option(
    "--analysis-timeout-seconds",
    type=click.IntRange(min=1),
    help="Timeout for analysis model calls. For codex-cli defaults to 600 when omitted.",
)
@click.option(
    "--analysis-max-retries",
    type=click.IntRange(min=0),
    help="Retry count for analysis model calls. For codex-cli defaults to 1 when omitted.",
)
@click.option(
    "--functional-checks",
    is_flag=True,
    help="Run optional setup/auth/workflow functional checks after generation.",
)
@click.option(
    "--functional-timeout-seconds",
    type=click.IntRange(min=1),
    help="Timeout for each functional validation step.",
)
def run_command(
    target: str | None,
    binary_name: str | None,
    model: str | None,
    forced_interface: str | None,
    output_dir: Path | None,
    probe_only: bool,
    force: bool,
    analysis_timeout_seconds: int | None,
    analysis_max_retries: int | None,
    functional_checks: bool,
    functional_timeout_seconds: int | None,
) -> None:
    """Run full or probe-only generation path for a single target."""

    try:
        classify_target(target, binary_name=binary_name)
        result = UseAnythingPipeline().run(
            target=target,
            binary_name=binary_name,
            model=model,
            forced_interface=forced_interface,
            output_dir=output_dir,
            probe_only=probe_only,
            force=force,
            analysis_timeout_seconds=analysis_timeout_seconds,
            analysis_max_retries=analysis_max_retries,
            functional_checks=functional_checks,
            functional_timeout_seconds=functional_timeout_seconds,
        )
    except (UnsupportedTargetError, ProbeError, AnalyzeError) as exc:
        raise click.ClickException(str(exc)) from exc

    if probe_only:
        payload = {
            "probe_result": result.probe_result.to_dict(),
            "rank_result": result.rank_result.to_dict(),
            "probe_only": True,
        }
        click.echo(json.dumps(payload, indent=2))
        return

    analysis_workflow_count = len(result.analysis.workflows) if result.analysis else 0
    emitted_workflow_count = _count_emitted_workflows(result.artifacts.skill_path if result.artifacts else None)
    workflow_count = emitted_workflow_count or analysis_workflow_count
    summary = {
        "interface_used": result.rank_result.primary.type,
        "skill_path": str(result.artifacts.skill_path) if result.artifacts else "",
        "token_counts": result.artifacts.token_counts if result.artifacts else {},
        "workflow_count": workflow_count,
        "analysis_workflow_count": analysis_workflow_count,
        "emitted_workflow_count": emitted_workflow_count,
        "analysis_sources": result.analysis.analysis_sources if result.analysis else [],
        "validation_passed": result.validation_report.passed if result.validation_report else False,
        "validation_errors": result.validation_report.errors if result.validation_report else [],
        "functional_checks_enabled": functional_checks,
        "functional_validation": result.functional_validation.to_dict() if result.functional_validation else None,
    }
    click.echo(json.dumps(summary, indent=2))


@cli.command("probe")
@click.argument("target", required=False)
@click.option("--binary", "binary_name", help="Probe a binary available on PATH")
def probe_command(target: str | None, binary_name: str | None) -> None:
    """Probe a target and list discovered interfaces."""

    try:
        classify_target(target, binary_name=binary_name)
        probe_result = Prober().probe_target(target, binary_name=binary_name)
    except (UnsupportedTargetError, ProbeError) as exc:
        raise click.ClickException(str(exc)) from exc

    payload = probe_result.to_dict()
    if probe_result.interfaces_found:
        ranking = Ranker().rank(probe_result)
        payload["ranking"] = ranking.to_dict()
    else:
        payload["ranking"] = None
    click.echo(json.dumps(payload, indent=2))


@cli.command("validate")
@click.argument("skill_dir", type=click.Path(path_type=Path, exists=True, file_okay=False))
def validate_command(skill_dir: Path) -> None:
    """Validate an existing generated skill directory."""

    report = Validator().validate_directory(skill_dir)
    click.echo(json.dumps(report.to_dict(), indent=2))
    if not report.passed:
        raise SystemExit(1)


def main() -> None:
    cli()


def _count_emitted_workflows(skill_path: Path | None) -> int:
    if skill_path is None or not skill_path.exists():
        return 0
    return sum(1 for line in skill_path.read_text(encoding="utf-8").splitlines() if line.startswith("### "))
