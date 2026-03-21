from __future__ import annotations

from pathlib import Path

import pytest

from use_anything.exceptions import UnsupportedTargetError
from use_anything.generate.generator import Generator
from use_anything.models import AnalyzerIR
from use_anything.pipeline import _default_output_slug
from use_anything.probe.targets import classify_target


@pytest.mark.security
@pytest.mark.parametrize("value", ["javascript:alert(1)", "file:///etc/passwd", "data:text/plain,hello"])
def test_classify_target_rejects_unsafe_url_schemes(value: str) -> None:
    with pytest.raises(UnsupportedTargetError):
        classify_target(value)


@pytest.mark.security
def test_default_output_slug_removes_shell_metacharacters() -> None:
    slug = _default_output_slug("https://docs.example.com/api;rm -rf / && echo hi")

    assert ";" not in slug
    assert "&" not in slug
    assert "/" not in slug
    assert "docs.example.com" in slug


@pytest.mark.security
def test_generator_blocks_script_symlink_escape(sample_analysis_dict, tmp_path: Path) -> None:
    ir = AnalyzerIR.from_dict(sample_analysis_dict)
    output_dir = tmp_path / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)

    outside = tmp_path / "outside"
    outside.mkdir(parents=True, exist_ok=True)
    (output_dir / "scripts").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="outside output directory"):
        Generator().generate(analysis=ir, output_dir=output_dir, source_interface="python_sdk")
