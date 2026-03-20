"""Probe adapters for URL, local-directory, and binary targets."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
import yaml

from use_anything.models import InterfaceCandidate
from use_anything.probe.interface_scanner import discover_interface_candidates, extract_links_from_html

OPENAPI_PREFLIGHT_PATHS = [
    "/openapi.json",
    "/openapi.yaml",
    "/swagger.json",
]
LLMS_PREFLIGHT_PATHS = [
    "/llms.txt",
    "/llms-full.txt",
]
SKILL_PREFLIGHT_PATHS = [
    "/.well-known/skills/default/skill.md",
]
VERIFIED_DOC_INTERFACE_TYPES = {"openapi_spec", "llms_txt", "existing_skill"}


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

    if html is not None:
        response_html = html
    else:
        status_code, _, fetched_html = _fetch_url(url)
        response_html = fetched_html if status_code == 200 else ""

    links = extract_links_from_html(response_html)
    absolute_links = [urljoin(url, link) for link in links]
    all_links = [url, *absolute_links]

    heuristic_candidates = discover_interface_candidates(
        source_location=url,
        urls=all_links,
        text=response_html,
    )
    verified_candidates = _verify_docs_interfaces(url, absolute_links)
    candidates = _merge_docs_candidates(
        heuristic_candidates=heuristic_candidates,
        verified_candidates=verified_candidates,
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

    return candidates, {
        "url": url,
        "discovered_links": all_links[:50],
        "verified_interface_types": sorted({candidate.type for candidate in verified_candidates}),
        "verified_interfaces": [
            {
                "type": candidate.type,
                "location": candidate.location,
                "status_code": candidate.metadata.get("status_code"),
                "content_type": candidate.metadata.get("content_type"),
            }
            for candidate in verified_candidates
        ],
    }


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

    return candidates, {
        "repo_url": repo_url,
        "tree_paths": tree_paths,
        "default_branch": payload.get("default_branch", ""),
        "resolved_ref": payload.get("resolved_ref", ""),
    }


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


def _fetch_url(url: str, timeout: float = 15.0) -> tuple[int, str, str]:
    try:
        response = httpx.get(url, timeout=timeout)
    except httpx.HTTPError:
        return 0, "", ""

    return response.status_code, response.headers.get("content-type", ""), response.text


def _fetch_github_tree(repo_url: str) -> dict[str, Any]:
    owner, repo = _parse_github_owner_repo(repo_url)
    if not owner or not repo:
        return {"tree_paths": []}

    repo_api_url = f"https://api.github.com/repos/{owner}/{repo}"
    default_branch = ""
    try:
        repo_response = httpx.get(repo_api_url, timeout=20.0)
        repo_response.raise_for_status()
        repo_payload = repo_response.json()
        if isinstance(repo_payload, dict):
            default_branch = str(repo_payload.get("default_branch") or "")
    except (httpx.HTTPError, ValueError):
        default_branch = ""

    refs_to_try = _ordered_unique([default_branch, "HEAD", "main", "master"])
    for ref in refs_to_try:
        api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{ref}?recursive=1"
        try:
            response = httpx.get(api_url, timeout=20.0)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            continue

        tree = payload.get("tree", []) if isinstance(payload, dict) else []
        paths = [entry.get("path", "") for entry in tree if isinstance(entry, dict)]
        return {
            "tree_paths": [path for path in paths if path],
            "default_branch": default_branch,
            "resolved_ref": ref,
        }

    return {"tree_paths": [], "default_branch": default_branch, "resolved_ref": ""}


def _parse_github_owner_repo(repo_url: str) -> tuple[str, str]:
    parsed = urlparse(repo_url)
    host = (parsed.netloc or "").lower()
    if host not in {"github.com", "www.github.com"}:
        return "", ""

    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) < 2:
        return "", ""

    owner = segments[0].strip()
    repo = segments[1].strip().removesuffix(".git")
    if not owner or not repo:
        return "", ""

    if len(segments) > 2 and not (len(segments) >= 4 and segments[2] in {"tree", "blob"} and segments[3].strip()):
        return "", ""

    return owner, repo


def _verify_docs_interfaces(base_url: str, discovered_links: list[str]) -> list[InterfaceCandidate]:
    verified: list[InterfaceCandidate] = []
    openapi_urls = _candidate_urls_for_docs_verification(
        base_url=base_url,
        discovered_links=discovered_links,
        preflight_paths=OPENAPI_PREFLIGHT_PATHS,
        required_signals=("openapi", "swagger"),
    )
    llms_urls = _candidate_urls_for_docs_verification(
        base_url=base_url,
        discovered_links=discovered_links,
        preflight_paths=LLMS_PREFLIGHT_PATHS,
        required_signals=("llms.txt", "llms-full.txt"),
    )
    skill_urls = _candidate_urls_for_docs_verification(
        base_url=base_url,
        discovered_links=discovered_links,
        preflight_paths=SKILL_PREFLIGHT_PATHS,
        required_signals=("skill.md", "/skills/", ".well-known/skills"),
    )

    for candidate_url in openapi_urls:
        candidate = _verify_openapi_endpoint(candidate_url)
        if candidate is not None:
            verified.append(candidate)
            break

    for candidate_url in llms_urls:
        candidate = _verify_llms_endpoint(candidate_url)
        if candidate is not None:
            verified.append(candidate)
            break

    for candidate_url in skill_urls:
        candidate = _verify_existing_skill_endpoint(candidate_url)
        if candidate is not None:
            verified.append(candidate)
            break

    return verified


def _candidate_urls_for_docs_verification(
    *,
    base_url: str,
    discovered_links: list[str],
    preflight_paths: list[str],
    required_signals: tuple[str, ...],
) -> list[str]:
    preflight_urls = [urljoin(base_url, path) for path in preflight_paths]
    discovered_matches = [
        link
        for link in discovered_links
        if any(signal in link.lower() for signal in required_signals)
    ]
    return _ordered_unique([*preflight_urls, *discovered_matches])


def _verify_openapi_endpoint(url: str) -> InterfaceCandidate | None:
    status_code, content_type, payload = _fetch_url(url)
    if status_code != 200 or not payload.strip():
        return None

    document = _parse_openapi_document(payload)
    if not document:
        return None

    if "openapi" not in document and "swagger" not in document:
        return None

    has_paths = isinstance(document.get("paths"), dict) and bool(document.get("paths"))
    notes = "Verified OpenAPI endpoint via HTTP probe"
    if not has_paths:
        notes = "Verified OpenAPI-like endpoint via HTTP probe (paths missing)"

    return InterfaceCandidate(
        type="openapi_spec",
        location=url,
        quality_score=0.96 if has_paths else 0.9,
        coverage="full" if has_paths else "partial",
        notes=notes,
        metadata={
            "verified": True,
            "verification_method": "http_probe",
            "status_code": status_code,
            "content_type": content_type,
            "openapi_version": document.get("openapi") or document.get("swagger") or "",
        },
    )


def _verify_llms_endpoint(url: str) -> InterfaceCandidate | None:
    status_code, content_type, payload = _fetch_url(url)
    stripped = payload.strip()
    if status_code != 200 or not stripped:
        return None
    if "<html" in stripped[:200].lower():
        return None

    excerpt = stripped[:240]
    return InterfaceCandidate(
        type="llms_txt",
        location=url,
        quality_score=0.84,
        coverage="partial",
        notes="Verified llms.txt-style documentation endpoint via HTTP probe",
        metadata={
            "verified": True,
            "verification_method": "http_probe",
            "status_code": status_code,
            "content_type": content_type,
            "evidence_excerpt": excerpt,
        },
    )


def _verify_existing_skill_endpoint(url: str) -> InterfaceCandidate | None:
    status_code, content_type, payload = _fetch_url(url)
    stripped = payload.strip()
    if status_code != 200 or not stripped:
        return None

    has_frontmatter = stripped.startswith("---")
    has_skill_heading = "\n# " in stripped or stripped.startswith("# ")
    if not has_frontmatter and not has_skill_heading:
        return None

    return InterfaceCandidate(
        type="existing_skill",
        location=url,
        quality_score=0.88,
        coverage="partial",
        notes="Verified existing skill markdown endpoint via HTTP probe",
        metadata={
            "verified": True,
            "verification_method": "http_probe",
            "status_code": status_code,
            "content_type": content_type,
        },
    )


def _parse_openapi_document(payload: str) -> dict[str, Any]:
    stripped = payload.strip()
    if not stripped:
        return {}

    try:
        loaded = json.loads(stripped)
        if isinstance(loaded, dict):
            return loaded
    except json.JSONDecodeError:
        pass

    try:
        loaded_yaml = yaml.safe_load(stripped)
    except yaml.YAMLError:
        return {}

    if isinstance(loaded_yaml, dict):
        return loaded_yaml
    return {}


def _merge_docs_candidates(
    *,
    heuristic_candidates: list[InterfaceCandidate],
    verified_candidates: list[InterfaceCandidate],
) -> list[InterfaceCandidate]:
    verified_by_type = {candidate.type: candidate for candidate in verified_candidates}

    merged: list[InterfaceCandidate] = []
    for candidate in heuristic_candidates:
        if candidate.type in VERIFIED_DOC_INTERFACE_TYPES:
            replacement = verified_by_type.get(candidate.type)
            if replacement and replacement not in merged:
                merged.append(replacement)
            continue
        merged.append(candidate)

    for candidate in verified_candidates:
        if all(existing.type != candidate.type for existing in merged):
            merged.append(candidate)

    return merged


def _ordered_unique(values: list[str]) -> list[str]:
    output: list[str] = []
    for value in values:
        if not value:
            continue
        if value in output:
            continue
        output.append(value)
    return output
