"""Main probe orchestrator."""

from __future__ import annotations

import os
import re

from use_anything.exceptions import ProbeError, UnsupportedTargetError
from use_anything.models import ProbeResult
from use_anything.probe.pypi import fetch_pypi_metadata, infer_interfaces_from_metadata

PACKAGE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class Prober:
    """Discover interfaces available for a given target."""

    def probe_target(self, target: str) -> ProbeResult:
        package_name = self._validate_and_classify_target(target)
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

    def _validate_and_classify_target(self, target: str) -> str:
        value = target.strip()
        if not value:
            raise UnsupportedTargetError("Only PyPI package names are supported in MVP; received empty target")

        if value.startswith("http://") or value.startswith("https://"):
            raise UnsupportedTargetError(
                "Only PyPI package names are supported in MVP. URL targets are not implemented yet."
            )

        if os.path.exists(value):
            raise UnsupportedTargetError(
                "Only PyPI package names are supported in MVP. Local directory targets are not implemented yet."
            )

        if value.startswith("npm:"):
            raise UnsupportedTargetError(
                "Only PyPI package names are supported in MVP. npm targets are not implemented yet."
            )

        if value.startswith("binary:"):
            raise UnsupportedTargetError(
                "Only PyPI package names are supported in MVP. binary targets are not implemented yet."
            )

        if not PACKAGE_NAME_RE.match(value):
            raise UnsupportedTargetError(
                f"Only PyPI package names are supported in MVP; '{target}' is not a valid package name"
            )

        return value
