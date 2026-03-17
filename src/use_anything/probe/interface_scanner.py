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
    normalized_paths = [item.lower() for item in (paths or [])]
    normalized_urls = [item.lower() for item in (urls or [])]
    normalized_text = text.lower()

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
            location=source_location,
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
            location=source_location,
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
            location=source_location,
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
            location=source_location,
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
            location=source_location,
            quality_score=0.72,
            coverage="partial",
            notes="Found Node package signals",
        ),
    )

    _add_if_present(
        candidates,
        key="rest_api_docs",
        present=_contains_any(
            normalized_paths + normalized_urls,
            ["/api", "/reference", "api-reference"],
        )
        or _contains_any([normalized_text], ["rest api", "endpoint", "http request"]),
        candidate=InterfaceCandidate(
            type="rest_api_docs",
            location=source_location,
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


def _add_if_present(
    candidates: OrderedDict[str, InterfaceCandidate],
    *,
    key: str,
    present: bool,
    candidate: InterfaceCandidate,
) -> None:
    if present and key not in candidates:
        candidates[key] = candidate
