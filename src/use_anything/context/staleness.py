"""Staleness evaluation for context documents."""

from __future__ import annotations

from datetime import date

from use_anything.context.models import ContextDoc, ContextDocFreshness

DEFAULT_STALE_DAYS = 30


def evaluate_doc_freshness(
    doc: ContextDoc,
    *,
    stale_after_days: int = DEFAULT_STALE_DAYS,
    today: date | None = None,
) -> ContextDocFreshness:
    reference_date = today or date.today()
    verified = doc.frontmatter.last_verified
    if verified is None:
        return ContextDocFreshness(
            stale=True,
            age_days=None,
            warning=f"{doc.path}: missing last_verified; treating as stale",
        )

    age_days = (reference_date - verified).days
    if age_days < 0:
        return ContextDocFreshness(
            stale=False,
            age_days=age_days,
            warning=f"{doc.path}: last_verified is in the future; treating as fresh",
        )

    is_stale = age_days > stale_after_days
    warning = None
    if is_stale:
        warning = (
            f"{doc.path}: last_verified is {age_days} days old "
            f"(threshold {stale_after_days}); treating as stale"
        )

    return ContextDocFreshness(stale=is_stale, age_days=age_days, warning=warning)
