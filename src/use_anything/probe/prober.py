"""Main probe orchestrator."""

from __future__ import annotations

from pathlib import Path

from use_anything.exceptions import ProbeError
from use_anything.models import ProbeResult
from use_anything.probe.adapters import probe_binary, probe_docs_url, probe_github_repo, probe_local_directory
from use_anything.probe.pypi import fetch_pypi_metadata, infer_interfaces_from_metadata
from use_anything.probe.targets import classify_target


class Prober:
    """Discover interfaces available for a given target."""

    def probe_target(self, target: str | None, *, binary_name: str | None = None) -> ProbeResult:
        classified = classify_target(target, binary_name=binary_name)

        if classified.target_type == "pypi_package":
            return self._probe_pypi(classified.normalized_target)

        if classified.target_type == "binary":
            candidates, metadata = probe_binary(classified.normalized_target)
            return ProbeResult(
                target=classified.normalized_target,
                target_type="binary",
                interfaces_found=candidates,
                recommended_interface=candidates[0].type if candidates else "cli_tool",
                reasoning="Binary targets use CLI probing first.",
                source_metadata=metadata,
            )

        if classified.target_type == "local_directory":
            return self._probe_local_directory(
                Path(classified.normalized_target),
                raw_target=classified.normalized_target,
            )

        if classified.target_type == "github_repo":
            return self._probe_url_target(classified.normalized_target, target_type="github_repo")

        if classified.target_type == "docs_url":
            return self._probe_url_target(classified.normalized_target, target_type="docs_url")

        raise ProbeError(f"Unsupported target type '{classified.target_type}'")

    def _probe_pypi(self, package_name: str) -> ProbeResult:
        metadata = fetch_pypi_metadata(package_name)
        candidates = infer_interfaces_from_metadata(package_name, metadata)
        if not candidates:
            raise ProbeError(f"No interfaces discovered for package '{package_name}'")

        info = metadata.get("info", {}) if isinstance(metadata, dict) else {}
        recommended = candidates[0].type

        return ProbeResult(
            target=package_name,
            target_type="pypi_package",
            interfaces_found=candidates,
            recommended_interface=recommended,
            reasoning=f"Selected '{recommended}' as the highest-scoring discovered interface.",
            source_metadata={
                "name": info.get("name", package_name),
                "version": info.get("version", "unknown"),
                "summary": info.get("summary", ""),
                "description": info.get("description", ""),
                "project_urls": info.get("project_urls") or {},
                "home_page": info.get("home_page", ""),
            },
        )

    def _probe_local_directory(self, directory: Path, *, raw_target: str) -> ProbeResult:
        candidates, metadata = probe_local_directory(directory)
        return ProbeResult(
            target=raw_target,
            target_type="local_directory",
            interfaces_found=candidates,
            recommended_interface=candidates[0].type if candidates else "python_sdk",
            reasoning="Detected local directory interfaces via file heuristics.",
            source_metadata=metadata,
        )

    def _probe_url_target(self, url: str, *, target_type: str) -> ProbeResult:
        if target_type == "github_repo":
            candidates, metadata = probe_github_repo(url)
        else:
            candidates, metadata = probe_docs_url(url)

        return ProbeResult(
            target=url,
            target_type=target_type,
            interfaces_found=candidates,
            recommended_interface=candidates[0].type if candidates else "rest_api_docs",
            reasoning=(
                f"Selected {candidates[0].type if candidates else 'rest_api_docs'} "
                "based on URL target heuristics."
            ),
            source_metadata=metadata,
        )
