from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from use_anything.exceptions import ProbeError, UnsupportedTargetError
from use_anything.models import InterfaceCandidate
from use_anything.probe.prober import Prober
from use_anything.probe.pypi import fetch_pypi_metadata, infer_interfaces_from_metadata


def test_infer_interfaces_prefers_python_sdk() -> None:
    metadata = {
        "info": {
            "name": "requests",
            "summary": "HTTP for Humans",
            "project_urls": {"Documentation": "https://requests.readthedocs.io/en/latest/"},
            "home_page": "https://requests.readthedocs.io",
        }
    }

    candidates = infer_interfaces_from_metadata("requests", metadata)
    assert candidates
    assert candidates[0].type == "python_sdk"


def test_prober_supports_docs_url_target() -> None:
    prober = Prober()
    result = prober.probe_target("https://docs.example.com/reference")

    assert result.target_type == "docs_url"
    assert result.interfaces_found


def test_prober_returns_probe_result_for_pypi(monkeypatch) -> None:
    sample_metadata = {
        "info": {
            "name": "requests",
            "version": "2.32.3",
            "summary": "HTTP for Humans",
            "project_urls": {"Documentation": "https://requests.readthedocs.io/en/latest/"},
            "home_page": "https://requests.readthedocs.io",
        }
    }

    monkeypatch.setattr(
        "use_anything.probe.prober.fetch_pypi_metadata",
        lambda package_name: sample_metadata,
    )

    prober = Prober()
    result = prober.probe_target("requests")

    assert result.target == "requests"
    assert result.target_type == "pypi_package"
    assert result.interfaces_found
    assert result.source_metadata["version"] == "2.32.3"


def test_prober_rejects_non_docs_non_github_url() -> None:
    prober = Prober()

    with pytest.raises(UnsupportedTargetError, match="docs URL or GitHub repository URL"):
        prober.probe_target("https://example.com")


def test_fetch_pypi_metadata_raises_probe_error_on_http_failure(monkeypatch) -> None:
    def fake_get(url: str, timeout: float = 15.0):  # noqa: ARG001
        request = httpx.Request("GET", url)
        response = httpx.Response(404, request=request)
        raise httpx.HTTPStatusError("missing", request=request, response=response)

    monkeypatch.setattr("use_anything.probe.pypi.httpx.get", fake_get)

    with pytest.raises(ProbeError, match="Failed to fetch package"):
        fetch_pypi_metadata("not-real-package")


def test_infer_interfaces_detects_rest_cli_and_existing_skill_signals() -> None:
    metadata = {
        "info": {
            "name": "demo",
            "summary": "CLI package with REST API endpoints and swagger docs",
            "description": "Command line utility with --help and OpenAPI support",
            "project_urls": {"Documentation": "https://docs.example.com/.well-known/skills/default/skill.md"},
            "home_page": "https://docs.example.com",
        }
    }

    candidates = infer_interfaces_from_metadata("demo", metadata)
    candidate_types = {candidate.type for candidate in candidates}

    assert "python_sdk" in candidate_types
    assert "rest_api_docs" in candidate_types
    assert "cli_tool" in candidate_types
    assert "existing_skill" in candidate_types


def test_prober_pypi_raises_when_no_candidates(monkeypatch) -> None:
    monkeypatch.setattr(
        "use_anything.probe.prober.fetch_pypi_metadata",
        lambda package_name: {"info": {"name": package_name}},
    )
    monkeypatch.setattr("use_anything.probe.prober.infer_interfaces_from_metadata", lambda package_name, metadata: [])

    with pytest.raises(ProbeError, match="No interfaces discovered"):
        Prober().probe_target("requests")


def test_prober_docs_target_defaults_recommended_interface_when_no_candidates(monkeypatch) -> None:
    monkeypatch.setattr("use_anything.probe.prober.probe_docs_url", lambda url: ([], {"url": url}))

    result = Prober().probe_target("https://docs.example.com/reference")

    assert result.target_type == "docs_url"
    assert result.recommended_interface == "rest_api_docs"
    assert result.interfaces_found == []


def test_prober_supports_binary_target(monkeypatch) -> None:
    monkeypatch.setattr(
        "use_anything.probe.prober.probe_binary",
        lambda binary_name: (
            [
                InterfaceCandidate(
                    type="cli_tool",
                    location=f"binary:{binary_name}",
                    quality_score=0.7,
                    coverage="partial",
                    notes="binary",
                )
            ],
            {"binary": binary_name},
        ),
    )

    result = Prober().probe_target(None, binary_name="ffmpeg")

    assert result.target_type == "binary"
    assert result.recommended_interface == "cli_tool"


def test_prober_supports_local_directory_target(tmp_path: Path, monkeypatch) -> None:
    directory = tmp_path / "demo"
    directory.mkdir()
    monkeypatch.setattr(
        "use_anything.probe.prober.probe_local_directory",
        lambda path: (
            [
                InterfaceCandidate(
                    type="python_sdk",
                    location=str(path),
                    quality_score=0.8,
                    coverage="partial",
                    notes="local",
                )
            ],
            {"path": str(path)},
        ),
    )

    result = Prober().probe_target(str(directory))

    assert result.target_type == "local_directory"
    assert result.recommended_interface == "python_sdk"


def test_prober_supports_github_repo_target(monkeypatch) -> None:
    monkeypatch.setattr(
        "use_anything.probe.prober.probe_github_repo",
        lambda url: (
            [
                InterfaceCandidate(
                    type="python_sdk",
                    location=url,
                    quality_score=0.8,
                    coverage="partial",
                    notes="repo",
                )
            ],
            {"repo_url": url},
        ),
    )

    result = Prober().probe_target("https://github.com/pallets/flask")

    assert result.target_type == "github_repo"
    assert result.interfaces_found[0].type == "python_sdk"
