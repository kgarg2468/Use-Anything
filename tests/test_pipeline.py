from __future__ import annotations

from pathlib import Path

import pytest

from use_anything.exceptions import UnsupportedTargetError
from use_anything.models import AnalyzerIR, ProbeResult, RankResult, ValidationReport
from use_anything.pipeline import UseAnythingPipeline


class FakeProber:
    def probe_target(self, target: str, *, binary_name: str | None = None) -> ProbeResult:
        from use_anything.models import InterfaceCandidate

        return ProbeResult(
            target=target,
            target_type="pypi_package",
            interfaces_found=[
                InterfaceCandidate(
                    type="python_sdk",
                    location=f"pypi:{target}",
                    quality_score=0.95,
                    coverage="full",
                    notes="Importable SDK",
                )
            ],
            source_metadata={"name": target, "version": "1.0.0", "summary": "demo"},
        )


class FakeRanker:
    def rank(self, probe_result: ProbeResult) -> RankResult:
        from use_anything.models import RankedInterface

        return RankResult(
            primary=RankedInterface(type="python_sdk", score=0.95, reasoning="best"),
            secondary=None,
            rejected=[],
        )


class FakeAnalyzer:
    def analyze(self, probe_result: ProbeResult, rank_result: RankResult) -> AnalyzerIR:
        return AnalyzerIR.from_dict(
            {
                "software": probe_result.target,
                "interface": "python_sdk",
                "version": "1.0.0",
                "setup": {
                    "install": f"pip install {probe_result.target}",
                    "auth": "No auth",
                    "env_vars": [],
                    "prerequisites": ["Python 3.10+"],
                },
                "capability_groups": [
                    {
                        "name": "Core",
                        "capabilities": [
                            {
                                "name": "Do thing",
                                "function": "pkg.do_thing()",
                                "params": {},
                                "returns": "dict",
                                "notes": "n/a",
                            }
                        ],
                    }
                ],
                "workflows": [
                    {
                        "name": "Run core flow",
                        "steps": ["1. Import package", "2. Call function", "3. Inspect result"],
                        "common_errors": ["missing dependency"],
                    },
                    {
                        "name": "Validate output",
                        "steps": ["1. Call function", "2. Check status", "3. Parse fields"],
                        "common_errors": ["wrong field names"],
                    },
                    {
                        "name": "Handle retries",
                        "steps": ["1. Catch exception", "2. Retry", "3. Log failure"],
                        "common_errors": ["retry loop"],
                    },
                ],
                "gotchas": [
                    "Use explicit versions.",
                    "Check return types.",
                    "Prefer idempotent operations.",
                    "Set timeouts.",
                    "Handle retries carefully.",
                ],
                "analysis_sources": [
                    "python_sdk:pypi:requests",
                ],
            }
        )


def test_pipeline_end_to_end_with_fakes(tmp_path: Path) -> None:
    output_dir = tmp_path / "generated"

    pipeline = UseAnythingPipeline(
        prober=FakeProber(),
        ranker=FakeRanker(),
        analyzer=FakeAnalyzer(),
    )

    result = pipeline.run(target="requests", output_dir=output_dir)

    assert result.validation_report.passed
    assert (output_dir / "SKILL.md").exists()


def test_pipeline_rejects_unknown_forced_interface() -> None:
    pipeline = UseAnythingPipeline(
        prober=FakeProber(),
        ranker=FakeRanker(),
        analyzer=FakeAnalyzer(),
    )

    with pytest.raises(UnsupportedTargetError, match="Unsupported forced interface"):
        pipeline.run(target="requests", forced_interface="banana_interface", probe_only=True)


def test_pipeline_passes_existing_skill_to_generator_when_not_forced(tmp_path: Path) -> None:
    existing_skill_path = tmp_path / "upstream-skill.md"
    existing_skill_path.write_text("---\nname: demo\ndescription: test\n---\n\n# demo\n")

    class ExistingSkillProber(FakeProber):
        def probe_target(self, target: str, *, binary_name: str | None = None) -> ProbeResult:
            from use_anything.models import InterfaceCandidate

            result = super().probe_target(target, binary_name=binary_name)
            result.interfaces_found.append(
                InterfaceCandidate(
                    type="existing_skill",
                    location=str(existing_skill_path),
                    quality_score=0.7,
                    coverage="partial",
                    notes="existing",
                )
            )
            return result

    class RecordingGenerator:
        def __init__(self) -> None:
            self.last_existing_skill: str | None = None
            self.last_force: bool | None = None

        def generate(self, analysis, output_dir, *, source_interface, existing_skill=None, force=False):  # noqa: ANN001
            self.last_existing_skill = existing_skill
            self.last_force = force
            from use_anything.models import GeneratedArtifacts

            skill_path = Path(output_dir) / "SKILL.md"
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            skill_path.write_text("---\nname: demo\ndescription: test\n---\n\n# demo\n")
            return GeneratedArtifacts(skill_path=skill_path, reference_paths={}, token_counts={}, line_counts={})

    class PassingValidator:
        def validate_directory(self, skill_dir):  # noqa: ANN001
            return ValidationReport(passed=True, errors=[], warnings=[], metrics={})

    generator = RecordingGenerator()
    pipeline = UseAnythingPipeline(
        prober=ExistingSkillProber(),
        ranker=FakeRanker(),
        analyzer=FakeAnalyzer(),
        generator=generator,
        validator=PassingValidator(),
    )

    pipeline.run(target="requests", output_dir=tmp_path / "generated", force=False)

    assert generator.last_existing_skill is not None
    assert "name: demo" in generator.last_existing_skill
    assert generator.last_force is False


def test_pipeline_skips_existing_skill_when_forced(tmp_path: Path) -> None:
    existing_skill_path = tmp_path / "upstream-skill.md"
    existing_skill_path.write_text("---\nname: demo\ndescription: test\n---\n\n# demo\n")

    class ExistingSkillProber(FakeProber):
        def probe_target(self, target: str, *, binary_name: str | None = None) -> ProbeResult:
            from use_anything.models import InterfaceCandidate

            result = super().probe_target(target, binary_name=binary_name)
            result.interfaces_found.append(
                InterfaceCandidate(
                    type="existing_skill",
                    location=str(existing_skill_path),
                    quality_score=0.7,
                    coverage="partial",
                    notes="existing",
                )
            )
            return result

    class RecordingGenerator:
        def __init__(self) -> None:
            self.last_existing_skill: str | None = "unexpected"
            self.last_force: bool | None = None

        def generate(self, analysis, output_dir, *, source_interface, existing_skill=None, force=False):  # noqa: ANN001
            self.last_existing_skill = existing_skill
            self.last_force = force
            from use_anything.models import GeneratedArtifacts

            skill_path = Path(output_dir) / "SKILL.md"
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            skill_path.write_text("---\nname: demo\ndescription: test\n---\n\n# demo\n")
            return GeneratedArtifacts(skill_path=skill_path, reference_paths={}, token_counts={}, line_counts={})

    class PassingValidator:
        def validate_directory(self, skill_dir):  # noqa: ANN001
            return ValidationReport(passed=True, errors=[], warnings=[], metrics={})

    generator = RecordingGenerator()
    pipeline = UseAnythingPipeline(
        prober=ExistingSkillProber(),
        ranker=FakeRanker(),
        analyzer=FakeAnalyzer(),
        generator=generator,
        validator=PassingValidator(),
    )

    pipeline.run(target="requests", output_dir=tmp_path / "generated", force=True)

    assert generator.last_existing_skill is None
    assert generator.last_force is True
