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


def test_validator_reports_directory_token_metrics(sample_analysis_dict, tmp_skill_dir: Path) -> None:
    ir = AnalyzerIR.from_dict(sample_analysis_dict)
    Generator().generate(ir, tmp_skill_dir, source_interface="python_sdk")

    report = Validator().validate_directory(tmp_skill_dir)

    assert report.passed is True
    assert "skill_tokens" in report.metrics
    assert "references_tokens" in report.metrics
    assert "skill_directory_tokens" in report.metrics
    assert report.metrics["skill_directory_tokens"] == (
        report.metrics["skill_tokens"] + report.metrics["references_tokens"]
    )


def test_validator_rejects_placeholder_text_and_bad_frontmatter(tmp_skill_dir: Path) -> None:
    skill_path = tmp_skill_dir / "SKILL.md"
    skill_path.write_text(
        """---
name: Bad Name
description: short
---

# Demo

## Setup

TODO add setup
""",
        encoding="utf-8",
    )

    report = Validator().validate_directory(tmp_skill_dir)

    assert report.passed is False
    assert any("Frontmatter 'name'" in error for error in report.errors)
    assert any("trigger phrases" in error for error in report.errors)
    assert any("placeholder text" in error.lower() for error in report.errors)


def test_validator_rejects_missing_references_directory(tmp_skill_dir: Path) -> None:
    skill_path = tmp_skill_dir / "SKILL.md"
    skill_path.write_text(
        """---
name: demo
description: Use this skill when asked to run API workflow task automation.
---

# demo

## Setup

pip install demo

## Core workflows

### one

1. run one

### two

1. run two

### three

1. run three

## Important constraints

- a
- b
- c
- d
- e

## Quick reference

| Operation | Command or Function |
|---|---|
| op1 | `a` |
| op2 | `b` |
| op3 | `c` |
| op4 | `d` |
| op5 | `e` |
| op6 | `f` |
| op7 | `g` |
| op8 | `h` |
| op9 | `i` |
| op10 | `j` |

## When to use references

See references/API_REFERENCE.md and references/WORKFLOWS.md and references/GOTCHAS.md.
""",
        encoding="utf-8",
    )

    report = Validator().validate_directory(tmp_skill_dir)

    assert report.passed is False
    assert any("references/ directory is missing" in error for error in report.errors)
