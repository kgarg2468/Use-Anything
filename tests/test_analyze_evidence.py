from __future__ import annotations

import httpx

from use_anything.analyze.evidence import mine_gotcha_evidence
from use_anything.models import InterfaceCandidate, ProbeResult


def _probe_result(*, target_type: str, target: str, project_urls: dict[str, str] | None = None) -> ProbeResult:
    return ProbeResult(
        target=target,
        target_type=target_type,
        interfaces_found=[
            InterfaceCandidate(
                type="python_sdk",
                location="pypi:demo" if target_type == "pypi_package" else target,
                quality_score=0.9,
                coverage="full",
                notes="demo",
            )
        ],
        source_metadata={
            "project_urls": project_urls or {},
            "home_page": "",
            "summary": "demo",
            "description": "demo",
        },
    )


def test_mine_gotcha_evidence_uses_github_target_repo(monkeypatch) -> None:
    observed: dict[str, str] = {}

    def fake_get(url: str, headers=None, timeout=10.0, params=None):  # noqa: ANN001, ARG001
        observed["url"] = url

        class Response:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> list[dict[str, object]]:
                return [
                    {
                        "title": "Authentication fails with expired token",
                        "body": "Users hit 401 auth failures unless refresh token is rotated.",
                        "html_url": "https://github.com/org/repo/issues/1",
                        "number": 1,
                    }
                ]

        return Response()

    monkeypatch.setattr("use_anything.analyze.evidence.httpx.get", fake_get)

    result = mine_gotcha_evidence(
        _probe_result(target_type="github_repo", target="https://github.com/org/repo")
    )

    assert observed["url"].endswith("/repos/org/repo/issues")
    assert result.warnings == []
    assert result.entries
    assert result.entries[0].source_type == "github_issue"
    assert result.entries[0].url == "https://github.com/org/repo/issues/1"


def test_mine_gotcha_evidence_resolves_repo_from_project_urls(monkeypatch) -> None:
    calls: dict[str, int] = {"count": 0}

    def fake_get(url: str, headers=None, timeout=10.0, params=None):  # noqa: ANN001, ARG001
        calls["count"] += 1

        class Response:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> list[dict[str, object]]:
                return [
                    {
                        "title": "Rate limit errors from pagination path",
                        "body": "429 is common when pagination loops do not back off.",
                        "html_url": "https://github.com/org/pkg/issues/10",
                        "number": 10,
                    }
                ]

        return Response()

    monkeypatch.setattr("use_anything.analyze.evidence.httpx.get", fake_get)

    probe_result = _probe_result(
        target_type="pypi_package",
        target="demo",
        project_urls={"Source": "https://github.com/org/pkg"},
    )
    result = mine_gotcha_evidence(probe_result)

    assert calls["count"] == 1
    assert result.entries[0].url == "https://github.com/org/pkg/issues/10"


def test_mine_gotcha_evidence_filters_prs_and_ranks_issue_relevance(monkeypatch) -> None:
    def fake_get(url: str, headers=None, timeout=10.0, params=None):  # noqa: ANN001, ARG001
        class Response:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> list[dict[str, object]]:
                return [
                    {
                        "title": "Docs update",
                        "body": "typo fix",
                        "html_url": "https://github.com/org/repo/pull/99",
                        "number": 99,
                        "pull_request": {"html_url": "https://github.com/org/repo/pull/99"},
                    },
                    {
                        "title": "Pagination returns duplicate rows under rate limit",
                        "body": "Users see 429 and duplicate pages unless cursor handling is explicit.",
                        "html_url": "https://github.com/org/repo/issues/3",
                        "number": 3,
                    },
                    {
                        "title": "Small typo in docs",
                        "body": "Spelling issue.",
                        "html_url": "https://github.com/org/repo/issues/4",
                        "number": 4,
                    },
                ]

        return Response()

    monkeypatch.setattr("use_anything.analyze.evidence.httpx.get", fake_get)

    result = mine_gotcha_evidence(
        _probe_result(target_type="github_repo", target="https://github.com/org/repo")
    )

    assert all(entry.url != "https://github.com/org/repo/pull/99" for entry in result.entries)
    assert result.entries[0].url == "https://github.com/org/repo/issues/3"
    assert result.entries[0].category in {"rate_limit", "pagination", "error"}


def test_mine_gotcha_evidence_gracefully_falls_back_when_github_unavailable(monkeypatch) -> None:
    def fake_get(url: str, headers=None, timeout=10.0, params=None):  # noqa: ANN001, ARG001
        raise httpx.HTTPStatusError(
            "rate limited",
            request=httpx.Request("GET", url),
            response=httpx.Response(403, request=httpx.Request("GET", url)),
        )

    monkeypatch.setattr("use_anything.analyze.evidence.httpx.get", fake_get)

    result = mine_gotcha_evidence(
        _probe_result(target_type="github_repo", target="https://github.com/org/repo")
    )

    assert result.entries == []
    assert any("github" in warning.lower() for warning in result.warnings)

