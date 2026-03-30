from __future__ import annotations

from datetime import date
from pathlib import Path

from use_anything.context.claims import extract_context_claims
from use_anything.context.models import ContextDoc, ContextDocFrontmatter
from use_anything.context.sections import is_generic_section, split_markdown_sections
from use_anything.context.staleness import evaluate_doc_freshness


def test_freshness_marks_missing_last_verified_as_stale() -> None:
    doc = ContextDoc(
        path=Path("supabase.md"),
        raw_text="",
        body="Body",
        frontmatter=ContextDocFrontmatter(),
    )

    result = evaluate_doc_freshness(doc, today=date(2026, 3, 29))

    assert result.stale is True
    assert result.age_days is None
    assert result.warning is not None


def test_freshness_marks_old_docs_as_stale() -> None:
    doc = ContextDoc(
        path=Path("supabase.md"),
        raw_text="",
        body="Body",
        frontmatter=ContextDocFrontmatter(last_verified=date(2026, 2, 1)),
    )

    result = evaluate_doc_freshness(doc, today=date(2026, 3, 29))

    assert result.stale is True
    assert result.age_days == 56


def test_freshness_marks_recent_docs_as_fresh() -> None:
    doc = ContextDoc(
        path=Path("supabase.md"),
        raw_text="",
        body="Body",
        frontmatter=ContextDocFrontmatter(last_verified=date(2026, 3, 21)),
    )

    result = evaluate_doc_freshness(doc, today=date(2026, 3, 29))

    assert result.stale is False
    assert result.age_days == 8


def test_generic_section_classifier() -> None:
    assert is_generic_section("Overview") is True
    assert is_generic_section("SDK Quickstart") is True
    assert is_generic_section("How this project uses Supabase") is False


def test_claim_extraction_trims_generic_sections() -> None:
    doc = ContextDoc(
        path=Path("supabase.md"),
        raw_text="",
        body=(
            "## Overview\n"
            "- Use SDK defaults.\n\n"
            "## How this project uses Supabase\n"
            "- Use anon key in browser client.\n"
            "- Keep service role on server-only paths.\n"
        ),
        frontmatter=ContextDocFrontmatter(),
    )

    sections = split_markdown_sections(doc.body)
    assert len(sections) == 2
    assert sections[0].generic is True
    assert sections[1].generic is False

    claims = extract_context_claims(doc)
    claim_text = [item.text for item in claims]
    assert "Use SDK defaults." not in claim_text
    assert "Use anon key in browser client." in claim_text
    assert "Keep service role on server-only paths." in claim_text
