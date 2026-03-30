"""Token budgeting for context claims."""

from __future__ import annotations

from collections import defaultdict

from use_anything.context.models import ContextBudgetResult, ContextClaim
from use_anything.utils.tokens import count_tokens

DEFAULT_CONTEXT_DOC_MAX_TOKENS = 800
DEFAULT_CONTEXT_DOC_TOTAL_MAX_TOKENS = 1600
MAX_TOKENS_PER_CLAIM = 120


def apply_context_budget(
    claims: list[ContextClaim],
    *,
    per_doc_max_tokens: int = DEFAULT_CONTEXT_DOC_MAX_TOKENS,
    total_max_tokens: int = DEFAULT_CONTEXT_DOC_TOTAL_MAX_TOKENS,
) -> ContextBudgetResult:
    accepted: list[ContextClaim] = []
    tokens_by_doc: dict[str, int] = defaultdict(int)
    total_tokens = 0
    dropped = 0
    truncated = 0

    for claim in claims:
        claim_tokens = count_tokens(claim.text)
        if claim_tokens > MAX_TOKENS_PER_CLAIM:
            truncated_text = _truncate_to_token_limit(claim.text, MAX_TOKENS_PER_CLAIM)
            claim = ContextClaim(
                text=truncated_text,
                source_path=claim.source_path,
                source_section=claim.source_section,
            )
            claim_tokens = count_tokens(claim.text)
            truncated += 1

        if claim_tokens <= 0:
            dropped += 1
            continue

        if tokens_by_doc[claim.source_path] + claim_tokens > per_doc_max_tokens:
            dropped += 1
            continue
        if total_tokens + claim_tokens > total_max_tokens:
            dropped += 1
            continue

        tokens_by_doc[claim.source_path] += claim_tokens
        total_tokens += claim_tokens
        accepted.append(claim)

    return ContextBudgetResult(
        claims=accepted,
        used_tokens=total_tokens,
        dropped_claims=dropped,
        truncated_claims=truncated,
    )


def _truncate_to_token_limit(text: str, max_tokens: int) -> str:
    words = text.split()
    if not words:
        return ""
    truncated_words: list[str] = []
    for word in words:
        candidate = " ".join([*truncated_words, word])
        if count_tokens(candidate) > max_tokens:
            break
        truncated_words.append(word)
    return " ".join(truncated_words)
