"""Conflict detection between context claims and local code signals."""

from __future__ import annotations

from use_anything.context.models import ContextClaim, ContextClaimConflict, ContextCodeSignal


def detect_claim_conflicts(
    claims: list[ContextClaim],
    code_signals: list[ContextCodeSignal],
) -> list[ContextClaimConflict]:
    conflicts: list[ContextClaimConflict] = []
    if not claims or not code_signals:
        return conflicts

    by_kind: dict[str, list[ContextCodeSignal]] = {}
    for signal in code_signals:
        by_kind.setdefault(signal.kind, []).append(signal)

    for claim in claims:
        claim_lower = claim.text.lower()

        if _mentions_service_role_in_browser(claim_lower):
            browser_signals = by_kind.get("supabase.browser_client", [])
            if browser_signals:
                conflicts.append(
                    ContextClaimConflict(
                        claim=claim,
                        signal=browser_signals[0],
                        reason="Claim suggests service-role usage in browser/client context.",
                    )
                )

        if "anon key should never be used" in claim_lower:
            anon_signals = by_kind.get("supabase.anon_key_usage", [])
            if anon_signals:
                conflicts.append(
                    ContextClaimConflict(
                        claim=claim,
                        signal=anon_signals[0],
                        reason="Claim denies anon key usage, but code references anon key.",
                    )
                )

        if "no rls" in claim_lower or "disable row level security" in claim_lower:
            rls_signals = by_kind.get("supabase.rls_or_migration", [])
            if rls_signals:
                conflicts.append(
                    ContextClaimConflict(
                        claim=claim,
                        signal=rls_signals[0],
                        reason="Claim conflicts with detected RLS/migration policy signals.",
                    )
                )

    return _dedupe_conflicts(conflicts)


def _mentions_service_role_in_browser(claim: str) -> bool:
    if "service role" not in claim and "service_role" not in claim:
        return False
    return any(marker in claim for marker in ("browser", "client-side", "frontend", "public client"))


def _dedupe_conflicts(conflicts: list[ContextClaimConflict]) -> list[ContextClaimConflict]:
    seen: set[tuple[str, str, str]] = set()
    output: list[ContextClaimConflict] = []
    for conflict in conflicts:
        key = (conflict.claim.text, conflict.signal.kind, conflict.signal.path)
        if key in seen:
            continue
        seen.add(key)
        output.append(conflict)
    return output
