from __future__ import annotations

from pathlib import Path

import pytest

from use_anything.generate.generator import Generator
from use_anything.models import AnalyzerIR


def test_generator_writes_skill_and_references(sample_analysis_dict, tmp_skill_dir: Path) -> None:
    ir = AnalyzerIR.from_dict(sample_analysis_dict)

    artifacts = Generator().generate(
        analysis=ir,
        output_dir=tmp_skill_dir,
        source_interface="python_sdk",
    )

    skill_path = artifacts.skill_path
    assert skill_path.exists()
    content = skill_path.read_text()
    assert "## Setup" in content
    assert "## Core workflows" in content
    assert "## Important constraints" in content

    assert (tmp_skill_dir / "references" / "API_REFERENCE.md").exists()
    assert (tmp_skill_dir / "references" / "WORKFLOWS.md").exists()
    assert (tmp_skill_dir / "references" / "GOTCHAS.md").exists()
    assert (tmp_skill_dir / "scripts" / "verify_setup.py").exists()
    assert "DEMO" not in (tmp_skill_dir / "scripts" / "verify_setup.py").read_text()


def test_generator_verify_setup_script_contains_env_vars(sample_analysis_dict, tmp_skill_dir: Path) -> None:
    sample_analysis_dict["setup"]["env_vars"] = ["STRIPE_API_KEY", "STRIPE_ACCOUNT_ID"]
    ir = AnalyzerIR.from_dict(sample_analysis_dict)

    Generator().generate(
        analysis=ir,
        output_dir=tmp_skill_dir,
        source_interface="python_sdk",
    )

    script = (tmp_skill_dir / "scripts" / "verify_setup.py").read_text()
    assert "STRIPE_API_KEY" in script
    assert "STRIPE_ACCOUNT_ID" in script


def test_generator_is_idempotent_for_same_analysis(sample_analysis_dict, tmp_skill_dir: Path) -> None:
    ir = AnalyzerIR.from_dict(sample_analysis_dict)
    generator = Generator()

    first = generator.generate(analysis=ir, output_dir=tmp_skill_dir, source_interface="python_sdk")
    first_snapshot = {
        "skill": first.skill_path.read_text(encoding="utf-8"),
        "api": first.reference_paths["api_reference"].read_text(encoding="utf-8"),
        "workflows": first.reference_paths["workflows"].read_text(encoding="utf-8"),
        "gotchas": first.reference_paths["gotchas"].read_text(encoding="utf-8"),
        "verify": first.script_paths["verify_setup"].read_text(encoding="utf-8"),
        "token_counts": first.token_counts,
        "line_counts": first.line_counts,
    }

    second = generator.generate(analysis=ir, output_dir=tmp_skill_dir, source_interface="python_sdk")
    second_snapshot = {
        "skill": second.skill_path.read_text(encoding="utf-8"),
        "api": second.reference_paths["api_reference"].read_text(encoding="utf-8"),
        "workflows": second.reference_paths["workflows"].read_text(encoding="utf-8"),
        "gotchas": second.reference_paths["gotchas"].read_text(encoding="utf-8"),
        "verify": second.script_paths["verify_setup"].read_text(encoding="utf-8"),
        "token_counts": second.token_counts,
        "line_counts": second.line_counts,
    }

    assert first_snapshot == second_snapshot


def test_generator_rejects_reference_symlink_escape(sample_analysis_dict, tmp_path: Path) -> None:
    ir = AnalyzerIR.from_dict(sample_analysis_dict)
    output_dir = tmp_path / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)

    outside = tmp_path / "outside"
    outside.mkdir(parents=True, exist_ok=True)
    (output_dir / "references").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="outside output directory"):
        Generator().generate(analysis=ir, output_dir=output_dir, source_interface="python_sdk")
