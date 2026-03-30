from __future__ import annotations

from pathlib import Path

from use_anything.context.code_signals import scan_supabase_code_signals
from use_anything.context.conflicts import detect_claim_conflicts
from use_anything.context.models import ContextClaim


def test_scan_supabase_code_signals_detects_browser_client_and_env(tmp_path: Path) -> None:
    src = tmp_path / "src" / "lib"
    src.mkdir(parents=True)
    client_file = src / "supabase.ts"
    client_file.write_text(
        (
            "import { createBrowserClient } from '@supabase/ssr';\n"
            "const client = createBrowserClient(process.env.SUPABASE_URL, process.env.SUPABASE_ANON_KEY);\n"
        ),
        encoding="utf-8",
    )
    sql_file = tmp_path / "supabase" / "migrations" / "2026_rls.sql"
    sql_file.parent.mkdir(parents=True)
    sql_file.write_text("alter table demo enable row level security;", encoding="utf-8")

    signals = scan_supabase_code_signals(tmp_path)
    kinds = {signal.kind for signal in signals}

    assert "supabase.browser_client" in kinds
    assert "supabase.env_var" in kinds
    assert "supabase.rls_or_migration" in kinds


def test_conflict_detector_flags_service_role_browser_claim(tmp_path: Path) -> None:
    supabase_file = tmp_path / "src" / "lib" / "supabase.ts"
    supabase_file.parent.mkdir(parents=True)
    supabase_file.write_text(
        (
            "import { createBrowserClient } from '@supabase/ssr';\n"
            "const client = createBrowserClient(url, anonKey);\n"
        ),
        encoding="utf-8",
    )
    signals = scan_supabase_code_signals(tmp_path)
    claims = [
        ContextClaim(
            text="Use service_role in browser client for all queries.",
            source_path="supabase.md",
            source_section="How this project uses Supabase",
        )
    ]

    conflicts = detect_claim_conflicts(claims, signals)

    assert len(conflicts) == 1
    assert "service-role usage in browser" in conflicts[0].reason
    assert conflicts[0].signal.kind == "supabase.browser_client"


def test_conflict_detector_ignores_non_conflicting_claim() -> None:
    claims = [
        ContextClaim(
            text="Use anon key in browser and service role only on server.",
            source_path="supabase.md",
            source_section="How this project uses Supabase",
        )
    ]
    conflicts = detect_claim_conflicts(claims, [])

    assert conflicts == []
