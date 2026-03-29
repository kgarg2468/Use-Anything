from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = PROJECT_ROOT / "skills" / "use-anything"


def test_skill_package_structure_exists() -> None:
    assert (SKILL_DIR / "SKILL.md").exists()
    assert (SKILL_DIR / "agents" / "openai.yaml").exists()
    assert (SKILL_DIR / "references" / "commands.md").exists()


def test_skill_frontmatter_and_prompt() -> None:
    skill_text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    openai_yaml = (SKILL_DIR / "agents" / "openai.yaml").read_text(encoding="utf-8")

    assert skill_text.startswith("---\n")
    assert "name: use-anything" in skill_text
    assert "description:" in skill_text
    assert "$use-anything" in skill_text
    assert "default_prompt:" in openai_yaml
    assert "$use-anything" in openai_yaml
