from __future__ import annotations

from pathlib import Path

import pytest

from use_anything.exceptions import UnsupportedTargetError
from use_anything.models import AnalyzerIR, ProbeResult, RankResult
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
