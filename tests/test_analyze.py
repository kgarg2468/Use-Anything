from __future__ import annotations

import pytest

from use_anything.analyze.analyzer import Analyzer
from use_anything.exceptions import AnalyzeError
from use_anything.models import InterfaceCandidate, ProbeResult, RankedInterface, RankResult


class FakeLLMClient:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def analyze(self, *, system_prompt: str, user_prompt: str, schema: dict) -> dict:
        assert "You are Use-Anything" in system_prompt
        assert "Target package" in user_prompt
        assert schema["type"] == "object"
        return self._payload


def _probe_and_rank() -> tuple[ProbeResult, RankResult]:
    probe = ProbeResult(
        target="requests",
        target_type="pypi_package",
        interfaces_found=[
            InterfaceCandidate(
                type="python_sdk",
                location="pypi:requests",
                quality_score=0.95,
                coverage="full",
                notes="Best interface",
            )
        ],
        source_metadata={"version": "2.32.3", "summary": "HTTP client"},
    )
    rank = RankResult(
        primary=RankedInterface(type="python_sdk", score=0.95, reasoning="best"),
        secondary=None,
        rejected=[],
    )
    return probe, rank


def test_analyzer_returns_typed_ir(sample_analysis_dict) -> None:
    probe, rank = _probe_and_rank()
    analyzer = Analyzer(llm_client=FakeLLMClient(sample_analysis_dict))

    ir = analyzer.analyze(probe_result=probe, rank_result=rank)

    assert ir.software == "requests"
    assert ir.interface == "python_sdk"
    assert len(ir.workflows) >= 3


def test_analyzer_rejects_invalid_payload() -> None:
    probe, rank = _probe_and_rank()
    analyzer = Analyzer(llm_client=FakeLLMClient({"bad": "shape"}))

    with pytest.raises(AnalyzeError):
        analyzer.analyze(probe_result=probe, rank_result=rank)
