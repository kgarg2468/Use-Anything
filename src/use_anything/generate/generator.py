"""Generation orchestrator for SKILL.md and reference files."""

from __future__ import annotations

from pathlib import Path

from use_anything.generate.reference_writer import (
    build_api_reference,
    build_gotchas_reference,
    build_workflows_reference,
)
from use_anything.generate.skill_merge import merge_skill_markdown
from use_anything.generate.skill_writer import render_skill_markdown
from use_anything.generate.verify_setup import build_verify_setup_script
from use_anything.models import AnalyzerIR, GeneratedArtifacts
from use_anything.utils.tokens import count_tokens


class Generator:
    """Generate all files for a skill directory."""

    def generate(
        self,
        analysis: AnalyzerIR,
        output_dir: Path | str,
        *,
        source_interface: str,
        existing_skill: str | None = None,
        force: bool = False,
    ) -> GeneratedArtifacts:
        target_dir = Path(output_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        skill_text = render_skill_markdown(analysis, source_interface=source_interface)
        if existing_skill and not force:
            skill_text = merge_skill_markdown(existing_skill=existing_skill, generated_skill=skill_text)
        skill_path = target_dir / "SKILL.md"
        skill_path.write_text(skill_text)

        references_dir = target_dir / "references"
        references_dir.mkdir(parents=True, exist_ok=True)

        api_ref_path = references_dir / "API_REFERENCE.md"
        workflows_ref_path = references_dir / "WORKFLOWS.md"
        gotchas_ref_path = references_dir / "GOTCHAS.md"

        api_ref_text = build_api_reference(analysis)
        workflows_ref_text = build_workflows_reference(analysis)
        gotchas_ref_text = build_gotchas_reference(analysis)

        api_ref_path.write_text(api_ref_text)
        workflows_ref_path.write_text(workflows_ref_text)
        gotchas_ref_path.write_text(gotchas_ref_text)

        scripts_dir = target_dir / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        verify_setup_path = scripts_dir / "verify_setup.py"
        verify_setup_text = build_verify_setup_script(analysis)
        verify_setup_path.write_text(verify_setup_text)

        token_counts = {
            "SKILL.md": count_tokens(skill_text),
            "references/API_REFERENCE.md": count_tokens(api_ref_text),
            "references/WORKFLOWS.md": count_tokens(workflows_ref_text),
            "references/GOTCHAS.md": count_tokens(gotchas_ref_text),
            "scripts/verify_setup.py": count_tokens(verify_setup_text),
        }

        line_counts = {
            "SKILL.md": len(skill_text.splitlines()),
            "references/API_REFERENCE.md": len(api_ref_text.splitlines()),
            "references/WORKFLOWS.md": len(workflows_ref_text.splitlines()),
            "references/GOTCHAS.md": len(gotchas_ref_text.splitlines()),
            "scripts/verify_setup.py": len(verify_setup_text.splitlines()),
        }

        return GeneratedArtifacts(
            skill_path=skill_path,
            reference_paths={
                "api_reference": api_ref_path,
                "workflows": workflows_ref_path,
                "gotchas": gotchas_ref_path,
            },
            token_counts=token_counts,
            line_counts=line_counts,
            script_paths={"verify_setup": verify_setup_path},
        )
