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


def test_ranker_scores_openapi_and_llms_above_cli() -> None:
    probe_result = ProbeResult(
        target="docs",
        target_type="docs_url",
        interfaces_found=[
            InterfaceCandidate(
                type="cli_tool",
                location="binary:tool",
                quality_score=0.9,
                coverage="partial",
                notes="cli",
            ),
            InterfaceCandidate(
                type="llms_txt",
                location="https://docs.example.dev/llms.txt",
                quality_score=0.8,
                coverage="partial",
                notes="llms",
            ),
            InterfaceCandidate(
                type="openapi_spec",
                location="https://docs.example.dev/openapi.json",
                quality_score=0.7,
                coverage="full",
                notes="openapi",
            ),
        ],
    )

    rank_result = Ranker().rank(probe_result)

    assert rank_result.primary.type == "openapi_spec"
    assert rank_result.secondary is not None
    assert rank_result.secondary.type == "llms_txt"


def test_ranker_applies_deterministic_tiebreak_priority() -> None:
    probe_result = ProbeResult(
        target="repo",
        target_type="github_repo",
        interfaces_found=[
            InterfaceCandidate(
                type="existing_skill",
                location="https://docs.example.dev/skill.md",
                quality_score=0.8,
                coverage="partial",
                notes="existing",
            ),
            InterfaceCandidate(
                type="python_sdk",
                location="https://github.com/example/repo",
                quality_score=0.8,
                coverage="partial",
                notes="sdk",
            ),
        ],
    )

    rank_result = Ranker().rank(probe_result)

    assert rank_result.primary.type == "python_sdk"
