"""Evidence mining helpers for gotcha extraction."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from use_anything.models import ProbeResult

MAX_ISSUES_TO_FETCH = 30
MAX_EVIDENCE_ENTRIES = 5
MAX_EXCERPT_CHARS = 260

_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "auth": ("auth", "token", "401", "unauthorized", "credential", "permission"),
    "rate_limit": ("rate limit", "429", "throttle", "quota", "backoff"),
    "pagination": ("pagination", "cursor", "page", "next page", "duplicate rows"),
    "breaking_change": ("breaking", "deprecated", "upgrade", "migration", "major version"),
    "error": ("error", "exception", "failed", "failure", "timeout", "invalid"),
}


@dataclass(frozen=True)
class GotchaEvidenceEntry:
    source_type: str
    source_label: str
    url: str
    title: str
    excerpt: str
    category: str
    relevance_score: float

    def source_ref(self) -> str:
        return f"{self.source_type}:{self.url}"


@dataclass(frozen=True)
class GotchaEvidenceResult:
    entries: list[GotchaEvidenceEntry]
    warnings: list[str]


def mine_gotcha_evidence(probe_result: ProbeResult) -> GotchaEvidenceResult:
    """Collect bounded gotcha evidence from GitHub issues when a repo is known."""

    repo = _resolve_github_repo(probe_result)
    if not repo:
        return GotchaEvidenceResult(
            entries=[],
            warnings=["GitHub repository source not found; using docs-only evidence"],
        )

    headers = {"Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"https://api.github.com/repos/{repo}/issues"
    try:
        response = httpx.get(
            url,
            headers=headers,
            timeout=10.0,
            params={"state": "all", "sort": "updated", "per_page": str(MAX_ISSUES_TO_FETCH)},
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        return GotchaEvidenceResult(
            entries=[],
            warnings=[f"GitHub issue evidence unavailable: {exc}; using docs-only evidence"],
        )

    payload = response.json()
    if not isinstance(payload, list):
        return GotchaEvidenceResult(
            entries=[],
            warnings=["GitHub issue evidence unavailable: unexpected response shape; using docs-only evidence"],
        )

    entries: list[GotchaEvidenceEntry] = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        if "pull_request" in raw:
            continue

        title = str(raw.get("title") or "").strip()
        body = str(raw.get("body") or "").strip()
        issue_url = str(raw.get("html_url") or "").strip()
        issue_number = raw.get("number")
        if not title or not issue_url:
            continue

        category, score = _score_issue(title=title, body=body)
        if score <= 0:
            continue

        excerpt = _truncate_text(body or title, MAX_EXCERPT_CHARS)
        entries.append(
            GotchaEvidenceEntry(
                source_type="github_issue",
                source_label=f"github:{repo}#{issue_number}",
                url=issue_url,
                title=title,
                excerpt=excerpt,
                category=category,
                relevance_score=round(score, 4),
            )
        )

    entries.sort(key=lambda item: item.relevance_score, reverse=True)
    return GotchaEvidenceResult(entries=entries[:MAX_EVIDENCE_ENTRIES], warnings=[])


def _resolve_github_repo(probe_result: ProbeResult) -> str:
    if probe_result.target_type == "github_repo":
        resolved = _owner_repo_from_url(probe_result.target)
        if resolved:
            return resolved

    metadata = probe_result.source_metadata if isinstance(probe_result.source_metadata, dict) else {}
    project_urls = metadata.get("project_urls", {})
    if isinstance(project_urls, dict):
        for value in project_urls.values():
            resolved = _owner_repo_from_url(str(value or ""))
            if resolved:
                return resolved

    home_page = str(metadata.get("home_page", "") or "")
    return _owner_repo_from_url(home_page)


def _owner_repo_from_url(value: str) -> str:
    if not value:
        return ""
    parsed = urlparse(value.strip())
    host = (parsed.netloc or "").lower()
    if host not in {"github.com", "www.github.com"}:
        return ""
    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) < 2:
        return ""
    owner = segments[0].strip()
    repo = segments[1].strip().removesuffix(".git")
    if not owner or not repo:
        return ""
    return f"{owner}/{repo}"


def _score_issue(*, title: str, body: str) -> tuple[str, float]:
    haystack = f"{title}\n{body}".lower()
    category_scores: dict[str, float] = {}

    for category, keywords in _CATEGORY_KEYWORDS.items():
        score = 0.0
        for keyword in keywords:
            hits = len(re.findall(re.escape(keyword), haystack))
            score += 0.25 * hits
        if score > 0:
            category_scores[category] = score

    if not category_scores:
        return "generic", 0.0

    best_category = max(category_scores, key=category_scores.get)
    # Small baseline keeps ranked items stable while preserving relative ordering.
    return best_category, 0.1 + category_scores[best_category]


def _truncate_text(value: str, limit: int) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]} [truncated]"
