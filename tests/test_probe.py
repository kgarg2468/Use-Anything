from __future__ import annotations

import pytest

from use_anything.exceptions import UnsupportedTargetError
from use_anything.probe.prober import Prober
from use_anything.probe.pypi import infer_interfaces_from_metadata


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
