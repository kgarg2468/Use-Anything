from __future__ import annotations

from pathlib import Path

from use_anything.generate.generator import Generator
from use_anything.models import AnalyzerIR
from use_anything.validate.validator import Validator


def test_validator_accepts_generated_skill(sample_analysis_dict, tmp_skill_dir: Path) -> None:
    ir = AnalyzerIR.from_dict(sample_analysis_dict)
    Generator().generate(ir, tmp_skill_dir, source_interface="python_sdk")

    report = Validator().validate_directory(tmp_skill_dir)

    assert report.passed is True
    assert report.errors == []


def test_validator_rejects_missing_frontmatter(tmp_skill_dir: Path) -> None:
    skill_path = tmp_skill_dir / "SKILL.md"
    skill_path.write_text("# invalid skill\n")

    report = Validator().validate_directory(tmp_skill_dir)

    assert report.passed is False
    assert any("frontmatter" in error.lower() for error in report.errors)


def test_validator_accepts_enhanced_skill_output(sample_analysis_dict, tmp_skill_dir: Path) -> None:
    ir = AnalyzerIR.from_dict(sample_analysis_dict)
    existing_skill = """---
name: requests
description: Existing requests helper
license: MIT
metadata:
  owner: team
---

# requests

## Setup

old setup details

## Team notes

Preserve this custom section.
"""

    Generator().generate(
        ir,
        tmp_skill_dir,
        source_interface="python_sdk",
        existing_skill=existing_skill,
        force=False,
    )

    report = Validator().validate_directory(tmp_skill_dir)

    assert report.passed is True


def test_validator_rejects_missing_required_reference_file(sample_analysis_dict, tmp_skill_dir: Path) -> None:
    ir = AnalyzerIR.from_dict(sample_analysis_dict)
    Generator().generate(ir, tmp_skill_dir, source_interface="python_sdk")

    (tmp_skill_dir / "references" / "GOTCHAS.md").unlink()
    report = Validator().validate_directory(tmp_skill_dir)

    assert report.passed is False
    assert any("Missing required reference file" in error for error in report.errors)


def test_validator_rejects_oversized_reference_tokens(sample_analysis_dict, tmp_skill_dir: Path) -> None:
    ir = AnalyzerIR.from_dict(sample_analysis_dict)
    Generator().generate(ir, tmp_skill_dir, source_interface="python_sdk")

    oversized = "word " * 11050
    (tmp_skill_dir / "references" / "API_REFERENCE.md").write_text(f"# Big file\n\n{oversized}")
    report = Validator().validate_directory(tmp_skill_dir)

    assert report.passed is False
    assert any("API_REFERENCE.md exceeds token limit" in error for error in report.errors)


def test_validator_rejects_skill_without_reference_links(sample_analysis_dict, tmp_skill_dir: Path) -> None:
    ir = AnalyzerIR.from_dict(sample_analysis_dict)
    Generator().generate(ir, tmp_skill_dir, source_interface="python_sdk")

    skill_path = tmp_skill_dir / "SKILL.md"
    skill_text = skill_path.read_text()
    for reference in ["references/API_REFERENCE.md", "references/WORKFLOWS.md", "references/GOTCHAS.md"]:
        skill_text = skill_text.replace(reference, "references/REMOVED.md")
    skill_path.write_text(skill_text)
    report = Validator().validate_directory(tmp_skill_dir)

    assert report.passed is False
    assert any("SKILL.md must reference references/API_REFERENCE.md" in error for error in report.errors)
