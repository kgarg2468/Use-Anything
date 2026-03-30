from __future__ import annotations

from use_anything.context.budget import apply_context_budget
from use_anything.context.models import ContextClaim


def test_context_budget_enforces_per_doc_limit() -> None:
    claims = [
        ContextClaim(
            text=f"Claim number {idx} uses anon key in browser client for scoped auth handling.",
            source_path="supabase.md",
            source_section="Project usage",
        )
        for idx in range(20)
    ]

    result = apply_context_budget(claims, per_doc_max_tokens=40, total_max_tokens=1000)

    assert len(result.claims) > 0
    assert result.dropped_claims > 0
    assert result.used_tokens <= 40


def test_context_budget_enforces_total_limit_across_docs() -> None:
    claims = [
        ContextClaim(
            text="Use anon key in browser and keep service role on server functions only.",
            source_path="supabase-a.md" if idx % 2 == 0 else "supabase-b.md",
            source_section="Project usage",
        )
        for idx in range(20)
    ]

    result = apply_context_budget(claims, per_doc_max_tokens=200, total_max_tokens=45)

    assert len(result.claims) > 0
    assert result.dropped_claims > 0
    assert result.used_tokens <= 45


def test_context_budget_truncates_oversized_claim() -> None:
    long_text = " ".join(f"token{idx}" for idx in range(400))
    claims = [
        ContextClaim(
            text=long_text,
            source_path="supabase.md",
            source_section="Project usage",
        )
    ]

    result = apply_context_budget(claims, per_doc_max_tokens=200, total_max_tokens=400)

    assert len(result.claims) == 1
    assert result.truncated_claims == 1
    assert result.used_tokens <= 120
