from __future__ import annotations

from pathlib import Path

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
