from __future__ import annotations

from pathlib import Path

from use_anything.context.parser import parse_context_doc


def test_parse_context_doc_without_frontmatter(tmp_path: Path) -> None:
    doc = tmp_path / "supabase.md"
    doc.write_text("## How this project uses Supabase\nUse anon key.\n", encoding="utf-8")

    result = parse_context_doc(doc)

    assert result.doc.body.startswith("## How this project")
    assert result.doc.frontmatter.last_verified is None
    assert result.doc.frontmatter.scope == ""
    assert result.warnings == []


def test_parse_context_doc_with_valid_frontmatter(tmp_path: Path) -> None:
    doc = tmp_path / "supabase.md"
    doc.write_text(
        (
            "---\n"
            "last_verified: 2026-03-20\n"
            "scope: project_specific\n"
            "owner: optx-platform\n"
            "applies_to:\n"
            "  - web\n"
            "  - api\n"
            "---\n"
            "## How this project uses Supabase\n"
            "- Use anon key in browser\n"
        ),
        encoding="utf-8",
    )

    result = parse_context_doc(doc)

    assert str(result.doc.frontmatter.last_verified) == "2026-03-20"
    assert result.doc.frontmatter.scope == "project_specific"
    assert result.doc.frontmatter.owner == "optx-platform"
    assert result.doc.frontmatter.applies_to == ["web", "api"]
    assert result.warnings == []


def test_parse_context_doc_warns_for_invalid_frontmatter(tmp_path: Path) -> None:
    doc = tmp_path / "supabase.md"
    doc.write_text(
        (
            "---\n"
            "last_verified: not-a-date\n"
            "applies_to: 123\n"
            "---\n"
            "Body\n"
        ),
        encoding="utf-8",
    )

    result = parse_context_doc(doc)

    assert result.doc.frontmatter.last_verified is None
    assert result.doc.frontmatter.applies_to == []
    assert len(result.warnings) == 2
    assert any("last_verified must be ISO date" in warning for warning in result.warnings)
    assert any("applies_to should be a string or list of strings" in warning for warning in result.warnings)


def test_parse_context_doc_accepts_string_applies_to(tmp_path: Path) -> None:
    doc = tmp_path / "supabase.md"
    doc.write_text(
        (
            "---\n"
            "applies_to: workers\n"
            "---\n"
            "Body\n"
        ),
        encoding="utf-8",
    )

    result = parse_context_doc(doc)

    assert result.doc.frontmatter.applies_to == ["workers"]
