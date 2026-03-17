from __future__ import annotations

from use_anything.models import InterfaceCandidate, ProbeResult
from use_anything.rank.ranker import Ranker


def test_ranker_prefers_python_sdk() -> None:
    probe_result = ProbeResult(
        target="requests",
        target_type="pypi_package",
        interfaces_found=[
            InterfaceCandidate(
                type="cli_tool",
                location="pypi:requests:cli",
                quality_score=0.4,
                coverage="partial",
                notes="CLI wrappers available",
            ),
            InterfaceCandidate(
                type="python_sdk",
                location="pypi:requests",
                quality_score=0.95,
                coverage="full",
                notes="Importable SDK",
            ),
        ],
    )

    rank_result = Ranker().rank(probe_result)

    assert rank_result.primary.type == "python_sdk"
    assert rank_result.secondary is not None
    assert rank_result.secondary.type == "cli_tool"
