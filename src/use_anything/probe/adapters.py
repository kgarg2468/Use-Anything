"""Probe adapters for URL, local-directory, and binary targets."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx

from use_anything.models import InterfaceCandidate
from use_anything.probe.interface_scanner import discover_interface_candidates, extract_links_from_html


def probe_binary(
    binary_name: str,
    *,
    command_output: dict[str, str] | None = None,
) -> tuple[list[InterfaceCandidate], dict[str, Any]]:
    """Probe a binary by inspecting `--help` and `--version` output."""

    output = command_output or {
        "help": _run_binary_command(binary_name, "--help"),
        "version": _run_binary_command(binary_name, "--version"),
    }
    text_blob = f"{output.get('help', '')}\n{output.get('version', '')}".strip()

    candidates = discover_interface_candidates(
        source_location=f"binary:{binary_name}",
        text=text_blob,
    )

    if not any(candidate.type == "cli_tool" for candidate in candidates):
        candidates.append(
            InterfaceCandidate(
                type="cli_tool",
                location=f"binary:{binary_name}",
                quality_score=0.7,
                coverage="partial",
                notes="Binary probing fallback to CLI interface",
            )
        )

    candidates.sort(key=lambda item: item.quality_score, reverse=True)
    return candidates, {"binary": binary_name, "command_output": output}


def probe_local_directory(directory: Path) -> tuple[list[InterfaceCandidate], dict[str, Any]]:
    """Probe a local directory by scanning common interface signals."""

    paths = []
    for path in directory.rglob("*"):
        if path.is_file():
            try:
                relative = str(path.relative_to(directory))
            except ValueError:
                relative = str(path)
            paths.append(relative)
        if len(paths) >= 1000:
            break

    candidates = discover_interface_candidates(
        source_location=str(directory),
        paths=paths,
    )
    return candidates, {"path": str(directory), "files_scanned": len(paths)}


def probe_docs_url(
    url: str,
    *,
    html: str | None = None,
) -> tuple[list[InterfaceCandidate], dict[str, Any]]:
    """Probe a documentation URL and discover interfaces from links/content."""

    response_html = html if html is not None else _fetch_text(url)
    links = extract_links_from_html(response_html)
    absolute_links = [urljoin(url, link) for link in links]

    candidates = discover_interface_candidates(
        source_location=url,
        urls=[url, *absolute_links],
        text=response_html,
    )

    if not any(candidate.type in {"rest_api_docs", "openapi_spec"} for candidate in candidates):
        candidates.append(
            InterfaceCandidate(
                type="rest_api_docs",
                location=url,
                quality_score=0.64,
                coverage="partial",
                notes="Documentation URL fallback to REST docs",
            )
        )
    candidates.sort(key=lambda item: item.quality_score, reverse=True)

    return candidates, {"url": url, "discovered_links": absolute_links[:50]}


def probe_github_repo(
    repo_url: str,
    *,
    tree_payload: dict[str, Any] | None = None,
) -> tuple[list[InterfaceCandidate], dict[str, Any]]:
    """Probe GitHub repository tree to identify interfaces."""

    payload = tree_payload or _fetch_github_tree(repo_url)
    tree_paths = [str(path) for path in payload.get("tree_paths", [])]

    candidates = discover_interface_candidates(
        source_location=repo_url,
        paths=tree_paths,
    )

    if not any(candidate.type in {"python_sdk", "node_sdk", "openapi_spec"} for candidate in candidates):
        candidates.append(
            InterfaceCandidate(
                type="python_sdk",
                location=repo_url,
                quality_score=0.6,
                coverage="partial",
                notes="GitHub repo fallback to SDK-style interface",
            )
        )
    candidates.sort(key=lambda item: item.quality_score, reverse=True)

    return candidates, {"repo_url": repo_url, "tree_paths": tree_paths}


def _run_binary_command(binary_name: str, arg: str) -> str:
    try:
        completed = subprocess.run(
            [binary_name, arg],
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return ""

    output = (completed.stdout or "") + "\n" + (completed.stderr or "")
    return output.strip()


def _fetch_text(url: str) -> str:
    try:
        response = httpx.get(url, timeout=15.0)
        response.raise_for_status()
        return response.text
    except httpx.HTTPError:
        return ""


def _fetch_github_tree(repo_url: str) -> dict[str, Any]:
    owner, repo = _parse_github_owner_repo(repo_url)
    if not owner or not repo:
        return {"tree_paths": []}

    api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1"
    try:
        response = httpx.get(api_url, timeout=20.0)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        return {"tree_paths": []}

    tree = payload.get("tree", []) if isinstance(payload, dict) else []
    paths = [entry.get("path", "") for entry in tree if isinstance(entry, dict)]
    return {"tree_paths": [path for path in paths if path]}


def _parse_github_owner_repo(repo_url: str) -> tuple[str, str]:
    trimmed = repo_url.removesuffix("/")
    parts = trimmed.split("/")
    if len(parts) < 2:
        return "", ""

    owner = parts[-2]
    repo = parts[-1].removesuffix(".git")
    return owner, repo
