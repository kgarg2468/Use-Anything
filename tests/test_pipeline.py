from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from use_anything.exceptions import UnsupportedTargetError
from use_anything.models import AnalyzerIR, ProbeResult, RankResult, ValidationReport
from use_anything.pipeline import UseAnythingPipeline, _default_output_slug


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
    assert result.functional_validation is None


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


def test_pipeline_applies_codex_default_analysis_limits(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    class RecordingAnalyzer:
        def __init__(self, *, model=None, timeout_seconds=None, max_retries=None):  # noqa: ANN001
            captured["model"] = model
            captured["timeout_seconds"] = timeout_seconds
            captured["max_retries"] = max_retries

        def analyze(self, probe_result: ProbeResult, rank_result: RankResult) -> AnalyzerIR:
            return FakeAnalyzer().analyze(probe_result, rank_result)

    monkeypatch.setattr("use_anything.pipeline.Analyzer", RecordingAnalyzer)
    pipeline = UseAnythingPipeline(
        prober=FakeProber(),
        ranker=FakeRanker(),
    )

    pipeline.run(target="requests", model="codex-cli", output_dir=tmp_path / "generated")

    assert captured["model"] == "codex-cli"
    assert captured["timeout_seconds"] == 600
    assert captured["max_retries"] == 1


def test_pipeline_allows_codex_analysis_limit_overrides(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    class RecordingAnalyzer:
        def __init__(self, *, model=None, timeout_seconds=None, max_retries=None):  # noqa: ANN001
            captured["model"] = model
            captured["timeout_seconds"] = timeout_seconds
            captured["max_retries"] = max_retries

        def analyze(self, probe_result: ProbeResult, rank_result: RankResult) -> AnalyzerIR:
            return FakeAnalyzer().analyze(probe_result, rank_result)

    monkeypatch.setattr("use_anything.pipeline.Analyzer", RecordingAnalyzer)
    pipeline = UseAnythingPipeline(
        prober=FakeProber(),
        ranker=FakeRanker(),
    )

    pipeline.run(
        target="requests",
        model="codex-cli",
        output_dir=tmp_path / "generated",
        analysis_timeout_seconds=720,
        analysis_max_retries=4,
    )

    assert captured["model"] == "codex-cli"
    assert captured["timeout_seconds"] == 720
    assert captured["max_retries"] == 4


def test_default_output_slug_sanitizes_url_targets() -> None:
    slug = _default_output_slug("https://github.com/pallets/flask")

    assert slug == "github.com-pallets-flask"
    assert ":" not in slug
    assert "/" not in slug


def test_default_output_slug_sanitizes_local_directory_targets(tmp_path: Path) -> None:
    project_dir = (tmp_path / "My Sample Project").resolve()
    project_dir.mkdir()

    slug = _default_output_slug(str(project_dir))

    assert ":" not in slug
    assert "/" not in slug
    assert "my-sample-project" in slug


def test_pipeline_runs_functional_validation_when_enabled(tmp_path: Path) -> None:
    class RecordingFunctionalValidator:
        def __init__(self) -> None:
            self.called = False
            self.timeout = None

        def run(self, analysis, artifacts, timeout_seconds):  # noqa: ANN001
            self.called = True
            self.timeout = timeout_seconds
            from use_anything.models import FunctionalCheckStepReport, FunctionalValidationReport

            return FunctionalValidationReport(
                enabled=True,
                passed=True,
                steps=[
                    FunctionalCheckStepReport(
                        name="setup_install",
                        command="pip install requests",
                        status="passed",
                        failure_category=None,
                        duration_ms=10,
                        stdout_excerpt="ok",
                        stderr_excerpt="",
                    )
                ],
                warnings=[],
            )

    recording = RecordingFunctionalValidator()

    pipeline = UseAnythingPipeline(
        prober=FakeProber(),
        ranker=FakeRanker(),
        analyzer=FakeAnalyzer(),
    )

    from use_anything import pipeline as pipeline_module

    original_runner = pipeline_module.run_functional_validation
    pipeline_module.run_functional_validation = recording.run
    try:
        result = pipeline.run(
            target="requests",
            output_dir=tmp_path / "generated",
            functional_checks=True,
            functional_timeout_seconds=44,
        )
    finally:
        pipeline_module.run_functional_validation = original_runner

    assert recording.called is True
    assert recording.timeout == 44
    assert result.functional_validation is not None
    assert result.functional_validation.enabled is True


def test_pipeline_uses_default_functional_timeout_when_omitted(tmp_path: Path) -> None:
    captured: dict[str, int] = {}

    def fake_runner(*, analysis, artifacts, timeout_seconds):  # noqa: ANN001
        captured["timeout_seconds"] = timeout_seconds
        from use_anything.models import FunctionalValidationReport

        return FunctionalValidationReport(enabled=True, passed=True, steps=[], warnings=[])

    from use_anything import pipeline as pipeline_module

    original_runner = pipeline_module.run_functional_validation
    pipeline_module.run_functional_validation = fake_runner
    try:
        result = UseAnythingPipeline(
            prober=FakeProber(),
            ranker=FakeRanker(),
            analyzer=FakeAnalyzer(),
        ).run(
            target="requests",
            output_dir=tmp_path / "generated",
            functional_checks=True,
            functional_timeout_seconds=None,
        )
    finally:
        pipeline_module.run_functional_validation = original_runner

    assert captured["timeout_seconds"] == 30
    assert result.functional_validation is not None
    assert result.functional_validation.passed is True


def test_pipeline_records_functional_runner_crash_as_failed_report(tmp_path: Path) -> None:
    def fake_runner(*, analysis, artifacts, timeout_seconds):  # noqa: ANN001, ARG001
        raise RuntimeError("runner crashed")

    from use_anything import pipeline as pipeline_module

    original_runner = pipeline_module.run_functional_validation
    pipeline_module.run_functional_validation = fake_runner
    try:
        result = UseAnythingPipeline(
            prober=FakeProber(),
            ranker=FakeRanker(),
            analyzer=FakeAnalyzer(),
        ).run(
            target="requests",
            output_dir=tmp_path / "generated",
            functional_checks=True,
        )
    finally:
        pipeline_module.run_functional_validation = original_runner

    assert result.functional_validation is not None
    assert result.functional_validation.enabled is True
    assert result.functional_validation.passed is False
    assert result.functional_validation.steps[0].name == "functional_validation"
    assert result.functional_validation.steps[0].status == "failed"
    assert result.functional_validation.steps[0].failure_category == "command_failed"
    assert "runner crashed" in result.functional_validation.steps[0].stderr_excerpt


def test_pipeline_loads_existing_skill_content_from_local_file(tmp_path: Path) -> None:
    skill_path = tmp_path / "existing.md"
    skill_path.write_text("# existing\n", encoding="utf-8")

    from use_anything.models import InterfaceCandidate

    content = UseAnythingPipeline()._load_existing_skill_content(
        [
            InterfaceCandidate(
                type="existing_skill",
                location=str(skill_path),
                quality_score=0.8,
                coverage="partial",
                notes="local",
            )
        ]
    )

    assert content == "# existing\n"


def test_pipeline_loads_existing_skill_content_from_url(monkeypatch) -> None:
    class FakeResponse:
        text = "# remote\n"

        def raise_for_status(self) -> None:
            return None

    monkeypatch.setattr("use_anything.pipeline.httpx.get", lambda url, timeout=15.0: FakeResponse())  # noqa: ARG005

    from use_anything.models import InterfaceCandidate

    content = UseAnythingPipeline()._load_existing_skill_content(
        [
            InterfaceCandidate(
                type="existing_skill",
                location="https://example.com/skill.md",
                quality_score=0.8,
                coverage="partial",
                notes="remote",
            )
        ]
    )

    assert content == "# remote\n"


def test_pipeline_existing_skill_url_http_error_returns_none(monkeypatch) -> None:
    def fake_get(url: str, timeout: float = 15.0):  # noqa: ARG001
        request = httpx.Request("GET", url)
        response = httpx.Response(500, request=request)
        raise httpx.HTTPStatusError("error", request=request, response=response)

    monkeypatch.setattr("use_anything.pipeline.httpx.get", fake_get)
    from use_anything.models import InterfaceCandidate

    content = UseAnythingPipeline()._load_existing_skill_content(
        [
            InterfaceCandidate(
                type="existing_skill",
                location="https://example.com/skill.md",
                quality_score=0.8,
                coverage="partial",
                notes="remote",
            )
        ]
    )

    assert content is None
