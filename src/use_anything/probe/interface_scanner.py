"""Shared interface discovery heuristics for non-PyPI probe targets."""

from __future__ import annotations

import re
from collections import OrderedDict

from use_anything.models import InterfaceCandidate


def discover_interface_candidates(
    *,
    source_location: str,
    paths: list[str] | None = None,
    urls: list[str] | None = None,
    text: str = "",
) -> list[InterfaceCandidate]:
    """Discover likely interfaces from filenames, URLs, and free-form text."""

    candidates: OrderedDict[str, InterfaceCandidate] = OrderedDict()
    path_pairs = [(item, item.lower()) for item in (paths or [])]
    url_pairs = [(item, item.lower()) for item in (urls or [])]
    normalized_paths = [item[1] for item in path_pairs]
    normalized_urls = [item[1] for item in url_pairs]
    normalized_text = text.lower()
    combined_pairs = [*path_pairs, *url_pairs]

    openapi_location = _first_match(
        combined_pairs,
        ["openapi.json", "openapi.yaml", "openapi.yml", "swagger.json", "swagger.yaml", "swagger.yml"],
    ) or source_location
    llms_location = _first_match(combined_pairs, ["llms.txt", "llms-full.txt"]) or source_location
    skill_location = (
        _first_match(combined_pairs, ["skill.md", "skills/default/skill.md", ".well-known/skills"])
        or source_location
    )
    python_location = _first_match(path_pairs, ["pyproject.toml", "setup.py", "requirements.txt"]) or source_location
    node_location = _first_match(path_pairs, ["package.json", "npm-shrinkwrap.json"]) or source_location
    rest_path_matches = [original for original, normalized in path_pairs if _is_rest_doc_path(normalized)]
    rest_url_matches = [
        original
        for original, normalized in url_pairs
        if _contains_any([normalized], ["/api", "/reference", "api-reference"])
    ]
    rest_location = (rest_path_matches[0] if rest_path_matches else "") or (
        rest_url_matches[0] if rest_url_matches else source_location
    )

    _add_if_present(
        candidates,
        key="openapi_spec",
        present=_contains_any(
            normalized_paths + normalized_urls,
            ["openapi.json", "openapi.yaml", "openapi.yml", "swagger.json", "swagger.yaml", "swagger.yml"],
        )
        or _contains_any([normalized_text], ["openapi", "swagger"]),
        candidate=InterfaceCandidate(
            type="openapi_spec",
            location=openapi_location,
            quality_score=0.95,
            coverage="full",
            notes="Discovered OpenAPI/Swagger signals",
        ),
    )

    _add_if_present(
        candidates,
        key="llms_txt",
        present=_contains_any(normalized_paths + normalized_urls, ["llms.txt", "llms-full.txt"]),
        candidate=InterfaceCandidate(
            type="llms_txt",
            location=llms_location,
            quality_score=0.82,
            coverage="partial",
            notes="Found llms.txt optimized docs",
        ),
    )

    _add_if_present(
        candidates,
        key="existing_skill",
        present=_contains_any(
            normalized_paths + normalized_urls,
            ["skill.md", "skills/default/skill.md", ".well-known/skills"],
        ),
        candidate=InterfaceCandidate(
            type="existing_skill",
            location=skill_location,
            quality_score=0.85,
            coverage="partial",
            notes="Found existing skill file",
        ),
    )

    _add_if_present(
        candidates,
        key="python_sdk",
        present=_contains_any(normalized_paths, ["pyproject.toml", "setup.py", "requirements.txt"])
        or _contains_any([normalized_text], ["pip install", "import "]),
        candidate=InterfaceCandidate(
            type="python_sdk",
            location=python_location,
            quality_score=0.78,
            coverage="partial",
            notes="Found Python package signals",
        ),
    )

    _add_if_present(
        candidates,
        key="node_sdk",
        present=_contains_any(normalized_paths, ["package.json", "npm-shrinkwrap.json"])
        or _contains_any([normalized_text], ["npm install", "require(", "import from"]),
        candidate=InterfaceCandidate(
            type="node_sdk",
            location=node_location,
            quality_score=0.72,
            coverage="partial",
            notes="Found Node package signals",
        ),
    )

    _add_if_present(
        candidates,
        key="rest_api_docs",
        present=bool(rest_path_matches or rest_url_matches)
        or _contains_any([normalized_text], ["rest api", "endpoint", "http request"]),
        candidate=InterfaceCandidate(
            type="rest_api_docs",
            location=rest_location,
            quality_score=0.68,
            coverage="partial",
            notes="Found REST API doc signals",
        ),
    )

    _add_if_present(
        candidates,
        key="cli_tool",
        present=_contains_any([normalized_text], ["--help", "command line", "usage:", "cli"]),
        candidate=InterfaceCandidate(
            type="cli_tool",
            location=source_location,
            quality_score=0.62,
            coverage="partial",
            notes="Found CLI usage/help signals",
        ),
    )

    if not candidates:
        candidates["rest_api_docs"] = InterfaceCandidate(
            type="rest_api_docs",
            location=source_location,
            quality_score=0.55,
            coverage="partial",
            notes="Fallback interface when no stronger signal is available",
        )

    return sorted(candidates.values(), key=lambda item: item.quality_score, reverse=True)


def extract_links_from_html(html: str) -> list[str]:
    """Extract href links from an HTML payload."""

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return re.findall(r"href=['\"]([^'\"]+)['\"]", html, flags=re.IGNORECASE)

    soup = BeautifulSoup(html, "html.parser")
    links = [str(link.get("href")) for link in soup.find_all("a") if link.get("href")]
    if links:
        return links
    return re.findall(r"href=['\"]([^'\"]+)['\"]", html, flags=re.IGNORECASE)


def _contains_any(haystacks: list[str], needles: list[str]) -> bool:
    for haystack in haystacks:
        for needle in needles:
            if needle in haystack:
                return True
    return False


def _is_rest_doc_path(path: str) -> bool:
    if not _is_doc_like_path(path):
        return False
    return _contains_any([path], ["/api", "/reference", "api-reference", "endpoints"])


def _is_doc_like_path(path: str) -> bool:
    doc_markers = (
        "docs/",
        "doc/",
        "reference/",
        "references/",
        "api/",
        "guides/",
        "readme",
    )
    doc_suffixes = (".md", ".rst", ".txt", ".html", ".htm")
    return path.startswith(doc_markers) or any(marker in path for marker in doc_markers) or path.endswith(doc_suffixes)


def _first_match(pairs: list[tuple[str, str]], needles: list[str]) -> str:
    for original, normalized in pairs:
        for needle in needles:
            if needle in normalized:
                return original
    return ""


def _add_if_present(
    candidates: OrderedDict[str, InterfaceCandidate],
    *,
    key: str,
    present: bool,
    candidate: InterfaceCandidate,
) -> None:
    if present and key not in candidates:
        candidates[key] = candidate
