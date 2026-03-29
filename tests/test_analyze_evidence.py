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
        if "api.github.com" in url:
            observed["url"] = url

            class GitHubResponse:
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

            return GitHubResponse()

        class StackOverflowResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, object]:
                return {"items": []}

        return StackOverflowResponse()

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
        if "api.github.com" in url:
            calls["count"] += 1

            class GitHubResponse:
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

            return GitHubResponse()

        class StackOverflowResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, object]:
                return {"items": []}

        return StackOverflowResponse()

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
        if "api.github.com" in url:
            class GitHubResponse:
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

            return GitHubResponse()

        class StackOverflowResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, object]:
                return {"items": []}

        return StackOverflowResponse()

    monkeypatch.setattr("use_anything.analyze.evidence.httpx.get", fake_get)

    result = mine_gotcha_evidence(
        _probe_result(target_type="github_repo", target="https://github.com/org/repo")
    )

    assert all(entry.url != "https://github.com/org/repo/pull/99" for entry in result.entries)
    assert result.entries[0].url == "https://github.com/org/repo/issues/3"
    assert result.entries[0].category in {"rate_limit", "pagination", "error"}


def test_mine_gotcha_evidence_gracefully_falls_back_when_github_unavailable(monkeypatch) -> None:
    def fake_get(url: str, headers=None, timeout=10.0, params=None):  # noqa: ANN001, ARG001
        if "api.github.com" in url:
            raise httpx.HTTPStatusError(
                "rate limited",
                request=httpx.Request("GET", url),
                response=httpx.Response(403, request=httpx.Request("GET", url)),
            )

        class StackOverflowResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, object]:
                return {
                    "items": [
                        {
                            "title": "Pagination loops can duplicate rows",
                            "body": "Use a stable cursor and backoff policy.",
                            "link": "https://stackoverflow.com/questions/12345/pagination-loops",
                            "question_id": 12345,
                            "score": 9,
                            "is_answered": True,
                            "accepted_answer_id": 67890,
                            "tags": ["pagination", "api", "rate-limit"],
                        }
                    ]
                }

        return StackOverflowResponse()

    monkeypatch.setattr("use_anything.analyze.evidence.httpx.get", fake_get)

    result = mine_gotcha_evidence(
        _probe_result(target_type="github_repo", target="https://github.com/org/repo")
    )

    assert result.entries
    assert result.entries[0].source_type == "stackoverflow"
    assert any("github" in warning.lower() for warning in result.warnings)


def test_mine_gotcha_evidence_includes_stackoverflow_entries(monkeypatch) -> None:
    def fake_get(url: str, headers=None, timeout=10.0, params=None):  # noqa: ANN001, ARG001
        if "api.github.com" in url:
            class GitHubResponse:
                def raise_for_status(self) -> None:
                    return None

                def json(self) -> list[dict[str, object]]:
                    return []

            return GitHubResponse()

        class StackOverflowResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, object]:
                return {
                    "items": [
                        {
                            "title": "Auth token expires unexpectedly",
                            "body": "401 errors unless refresh is scheduled before expiry.",
                            "link": "https://stackoverflow.com/questions/222/auth-token-expires",
                            "question_id": 222,
                            "score": 15,
                            "is_answered": True,
                            "accepted_answer_id": 333,
                            "tags": ["auth", "token"],
                        }
                    ]
                }

        return StackOverflowResponse()

    monkeypatch.setattr("use_anything.analyze.evidence.httpx.get", fake_get)

    result = mine_gotcha_evidence(
        _probe_result(target_type="pypi_package", target="requests")
    )

    assert result.entries
    assert result.entries[0].source_type == "stackoverflow"
    assert result.entries[0].url == "https://stackoverflow.com/questions/222/auth-token-expires"


def test_mine_gotcha_evidence_dedupes_cross_source_duplicates(monkeypatch) -> None:
    def fake_get(url: str, headers=None, timeout=10.0, params=None):  # noqa: ANN001, ARG001
        if "api.github.com" in url:
            class GitHubResponse:
                def raise_for_status(self) -> None:
                    return None

                def json(self) -> list[dict[str, object]]:
                    return [
                        {
                            "title": "Auth token expires unexpectedly",
                            "body": "Refresh tokens before expiry to avoid 401.",
                            "html_url": "https://github.com/org/repo/issues/1",
                            "number": 1,
                        }
                    ]

            return GitHubResponse()

        class StackOverflowResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, object]:
                return {
                    "items": [
                        {
                            "title": "Auth token expires unexpectedly!!!",
                            "body": "Refresh tokens before expiry to avoid 401.",
                            "link": "https://stackoverflow.com/questions/444/auth-token-expires",
                            "question_id": 444,
                            "score": 10,
                            "is_answered": True,
                            "accepted_answer_id": 445,
                            "tags": ["auth", "token"],
                        }
                    ]
                }

        return StackOverflowResponse()

    monkeypatch.setattr("use_anything.analyze.evidence.httpx.get", fake_get)

    result = mine_gotcha_evidence(
        _probe_result(target_type="github_repo", target="https://github.com/org/repo")
    )

    assert len(result.entries) == 1
    assert result.entries[0].title == "Auth token expires unexpectedly"
