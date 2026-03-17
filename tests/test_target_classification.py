from __future__ import annotations

from pathlib import Path

import pytest

from use_anything.exceptions import UnsupportedTargetError
from use_anything.probe.targets import classify_target


def test_classify_pypi_package_name() -> None:
    result = classify_target("requests")

    assert result.target_type == "pypi_package"
    assert result.normalized_target == "requests"


def test_classify_github_repo_url() -> None:
    result = classify_target("https://github.com/pallets/flask")

    assert result.target_type == "github_repo"
    assert result.normalized_target == "https://github.com/pallets/flask"


def test_classify_docs_url() -> None:
    result = classify_target("https://docs.python-requests.org/en/latest/")

    assert result.target_type == "docs_url"
    assert result.normalized_target.startswith("https://docs.python-requests.org")


def test_classify_local_directory(tmp_path: Path) -> None:
    project_dir = tmp_path / "sample"
    project_dir.mkdir()

    result = classify_target(str(project_dir))

    assert result.target_type == "local_directory"
    assert result.normalized_target == str(project_dir.resolve())


def test_classify_binary_option() -> None:
    result = classify_target(None, binary_name="ffmpeg")

    assert result.target_type == "binary"
    assert result.normalized_target == "ffmpeg"


@pytest.mark.parametrize(
    ("target", "binary_name", "expected"),
    [
        (None, None, "Either TARGET or --binary must be provided"),
        ("requests", "ffmpeg", "Provide only one target source"),
        ("", None, "Either TARGET or --binary must be provided"),
        ("not valid target!", None, "valid package name"),
        ("https://example.com", None, "docs URL or GitHub repository URL"),
    ],
)
def test_classify_invalid_inputs(target: str | None, binary_name: str | None, expected: str) -> None:
    with pytest.raises(UnsupportedTargetError, match=expected):
        classify_target(target, binary_name=binary_name)
