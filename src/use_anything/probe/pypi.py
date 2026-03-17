"""PyPI target probing utilities."""

from __future__ import annotations

import re
from typing import Any

import httpx

from use_anything.exceptions import ProbeError
from use_anything.models import InterfaceCandidate

PYPI_URL_TEMPLATE = "https://pypi.org/pypi/{package}/json"


def fetch_pypi_metadata(package_name: str, timeout: float = 15.0) -> dict[str, Any]:
    """Fetch package metadata from the PyPI JSON API."""

    try:
        response = httpx.get(PYPI_URL_TEMPLATE.format(package=package_name), timeout=timeout)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ProbeError(f"Failed to fetch package '{package_name}' from PyPI: {exc}") from exc

    payload = response.json()
    if not isinstance(payload, dict) or "info" not in payload:
        raise ProbeError(f"PyPI metadata for '{package_name}' is missing expected structure")
    return payload


def infer_interfaces_from_metadata(package_name: str, metadata: dict[str, Any]) -> list[InterfaceCandidate]:
    """Infer candidate interfaces from package metadata with deterministic heuristics."""

    info = metadata.get("info", {}) if isinstance(metadata, dict) else {}
    project_urls = info.get("project_urls") or {}
    description_text = " ".join(
        [
            str(info.get("summary", "")),
            str(info.get("description", "")),
            " ".join(str(value) for value in project_urls.values()),
            str(info.get("home_page", "")),
        ]
    ).lower()

    docs_url = _pick_docs_url(info)
    candidates: list[InterfaceCandidate] = [
        InterfaceCandidate(
            type="python_sdk",
            location=f"pypi:{package_name}",
            quality_score=0.92,
            coverage="full",
            notes="Installable Python SDK from PyPI",
            metadata={"docs_url": docs_url},
        )
    ]

    if _looks_like_rest_docs(description_text):
        candidates.append(
            InterfaceCandidate(
                type="rest_api_docs",
                location=docs_url or "metadata:project_urls",
                quality_score=0.66,
                coverage="partial",
                notes="REST docs signals discovered in package metadata",
                metadata={"docs_url": docs_url},
            )
        )

    if _looks_like_cli_tool(description_text):
        candidates.append(
            InterfaceCandidate(
                type="cli_tool",
                location=f"pypi:{package_name}:cli",
                quality_score=0.58,
                coverage="partial",
                notes="CLI-related signals detected in docs/summary",
                metadata={"docs_url": docs_url},
            )
        )

    if docs_url and re.search(r"skills?/|skill\.md|\.well-known/skills", docs_url, re.IGNORECASE):
        candidates.append(
            InterfaceCandidate(
                type="existing_skill",
                location=docs_url,
                quality_score=0.8,
                coverage="partial",
                notes="Potential pre-existing skill discovered from docs URL",
                metadata={"docs_url": docs_url},
            )
        )

    candidates.sort(key=lambda item: item.quality_score, reverse=True)
    return candidates


def _pick_docs_url(info: dict[str, Any]) -> str:
    project_urls = info.get("project_urls") or {}
    for key in ["Documentation", "Docs", "Homepage", "Home"]:
        value = project_urls.get(key)
        if value:
            return str(value)
    return str(info.get("home_page") or "")


def _looks_like_rest_docs(text: str) -> bool:
    return any(signal in text for signal in ["rest api", "/api/", "endpoints", "openapi", "swagger"]) 


def _looks_like_cli_tool(text: str) -> bool:
    return any(signal in text for signal in ["command line", "cli", "--help", "console script", "terminal"])
