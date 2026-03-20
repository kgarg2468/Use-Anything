"""Target classification helpers for probe and CLI paths."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from use_anything.exceptions import UnsupportedTargetError

PACKAGE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
BINARY_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


@dataclass(frozen=True)
class ClassifiedTarget:
    target_type: str
    normalized_target: str


def classify_target(target: str | None, *, binary_name: str | None = None) -> ClassifiedTarget:
    """Classify a target as supported probe target type."""

    normalized_target = (target or "").strip()
    normalized_binary = (binary_name or "").strip()

    if normalized_target and normalized_binary:
        raise UnsupportedTargetError("Provide only one target source: TARGET or --binary")

    if normalized_binary:
        if not BINARY_NAME_RE.match(normalized_binary):
            raise UnsupportedTargetError("--binary expects a valid executable name")
        return ClassifiedTarget(target_type="binary", normalized_target=normalized_binary)

    if not normalized_target:
        raise UnsupportedTargetError("Either TARGET or --binary must be provided")

    if _is_url(normalized_target):
        parsed = urlparse(normalized_target)
        host = (parsed.netloc or "").lower()
        path = parsed.path.rstrip("/")

        if host in {"github.com", "www.github.com"}:
            normalized_repo = _normalize_github_repo_url(normalized_target)
            if normalized_repo:
                return ClassifiedTarget(target_type="github_repo", normalized_target=normalized_repo)

        if _looks_like_docs_url(host, path):
            return ClassifiedTarget(target_type="docs_url", normalized_target=normalized_target.rstrip("/"))

        raise UnsupportedTargetError(
            "URL targets must be a docs URL or GitHub repository URL"
        )

    if os.path.isdir(normalized_target):
        return ClassifiedTarget(target_type="local_directory", normalized_target=str(Path(normalized_target).resolve()))

    if os.path.exists(normalized_target):
        raise UnsupportedTargetError("Local path targets must be directories")

    if PACKAGE_NAME_RE.match(normalized_target):
        return ClassifiedTarget(target_type="pypi_package", normalized_target=normalized_target)

    raise UnsupportedTargetError(
        f"Only a valid package name, supported URL, or local directory is allowed; got '{target}'"
    )


def _is_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def _looks_like_github_repo(path: str) -> bool:
    segments = [segment for segment in path.split("/") if segment]
    return len(segments) >= 2


def _normalize_github_repo_url(url: str) -> str | None:
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    if host not in {"github.com", "www.github.com"}:
        return None

    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) < 2:
        return None

    owner = segments[0].strip()
    repo = segments[1].strip().removesuffix(".git")
    if not owner or not repo:
        return None

    if len(segments) == 2:
        return f"https://github.com/{owner}/{repo}"

    if len(segments) >= 4 and segments[2] in {"tree", "blob"} and segments[3].strip():
        return f"https://github.com/{owner}/{repo}"

    return None


def _looks_like_docs_url(host: str, path: str) -> bool:
    path_lower = path.lower()
    return (
        host.startswith("docs.")
        or "readthedocs" in host
        or "/docs" in path_lower
        or "/reference" in path_lower
        or "/api" in path_lower
    )
