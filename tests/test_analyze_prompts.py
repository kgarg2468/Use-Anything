from __future__ import annotations

from use_anything.analyze.prompts import build_analysis_prompt
from use_anything.models import InterfaceCandidate, ProbeResult, RankedInterface, RankResult


def test_analysis_prompt_requires_grounded_outputs() -> None:
    probe_result = ProbeResult(
        target="requests",
        target_type="pypi_package",
        interfaces_found=[
            InterfaceCandidate(
                type="python_sdk",
                location="pypi:requests",
                quality_score=0.9,
                coverage="full",
                notes="sdk",
            )
        ],
        source_metadata={"version": "2.0.0", "summary": "HTTP library", "project_urls": {}},
    )
    rank_result = RankResult(
        primary=RankedInterface(type="python_sdk", score=0.9, reasoning="best"),
        secondary=None,
        rejected=[],
    )

    prompt = build_analysis_prompt(
        probe_result=probe_result,
        rank_result=rank_result,
        interface_context="Context excerpt",
        analysis_sources=["python_sdk:pypi:requests"],
    )

    assert "Do not invent commands/functions/endpoints" in prompt
    assert "Tie workflows and gotchas to provided evidence" in prompt
    assert "analysis_sources" in prompt


def test_analysis_prompt_applies_budget_for_large_github_context() -> None:
    probe_result = ProbeResult(
        target="https://github.com/example/project",
        target_type="github_repo",
        interfaces_found=[
            InterfaceCandidate(
                type="python_sdk",
                location="https://github.com/example/project",
                quality_score=0.9,
                coverage="partial",
                notes="repo",
            )
        ],
        source_metadata={"version": "main", "summary": "repo summary", "project_urls": {"repo": "x" * 5000}},
    )
    rank_result = RankResult(
        primary=RankedInterface(type="python_sdk", score=0.9, reasoning="best"),
        secondary=None,
        rejected=[],
    )

    prompt = build_analysis_prompt(
        probe_result=probe_result,
        rank_result=rank_result,
        interface_context="A" * 10000,
        analysis_sources=["python_sdk:https://github.com/example/project"],
    )

    assert "[truncated]" in prompt
    assert len(prompt) < 12000
