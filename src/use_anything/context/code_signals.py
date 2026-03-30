"""Local repository signal extraction for Supabase-oriented context docs."""

from __future__ import annotations

import re
from pathlib import Path

from use_anything.context.models import ContextCodeSignal

MAX_FILES_SCANNED = 1200
SUPPORTED_SUFFIXES = {
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".py",
    ".sql",
    ".env",
    ".md",
    ".json",
    ".yaml",
    ".yml",
}

ENV_PATTERN = re.compile(r"\bSUPABASE_[A-Z0-9_]+\b")


def scan_supabase_code_signals(project_dir: Path | str) -> list[ContextCodeSignal]:
    root = Path(project_dir)
    if not root.exists() or not root.is_dir():
        return []

    paths = _candidate_paths(root)
    signals: list[ContextCodeSignal] = []
    for path in paths:
        content = _read_text(path)
        if not content:
            continue
        relative_path = str(path.relative_to(root))
        signals.extend(_extract_signals_from_content(content, relative_path))

    return _dedupe_signals(signals)


def _candidate_paths(root: Path) -> list[Path]:
    candidates: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_SUFFIXES and path.name not in {".env", ".env.local"}:
            continue
        if ".git/" in str(path):
            continue
        candidates.append(path)
        if len(candidates) >= MAX_FILES_SCANNED:
            break
    return candidates


def _extract_signals_from_content(content: str, relative_path: str) -> list[ContextCodeSignal]:
    lowered = content.lower()
    signals: list[ContextCodeSignal] = []

    if "createserverclient" in lowered or "create_server_client" in lowered:
        signals.append(ContextCodeSignal(kind="supabase.server_client", value="present", path=relative_path))
    if "createbrowserclient" in lowered or "create_browser_client" in lowered:
        signals.append(ContextCodeSignal(kind="supabase.browser_client", value="present", path=relative_path))
    if "createservice" in lowered and "supabase" in lowered:
        signals.append(ContextCodeSignal(kind="supabase.service_client", value="present", path=relative_path))
    if "createclient(" in lowered and "supabase" in lowered:
        signals.append(ContextCodeSignal(kind="supabase.create_client_call", value="present", path=relative_path))
    if "service_role" in lowered:
        signals.append(ContextCodeSignal(kind="supabase.service_role_usage", value="present", path=relative_path))
    if "anon key" in lowered or "anon_key" in lowered or "anon-key" in lowered:
        signals.append(ContextCodeSignal(kind="supabase.anon_key_usage", value="present", path=relative_path))
    if "/supabase/migrations" in lowered or "create policy" in lowered or "enable row level security" in lowered:
        signals.append(ContextCodeSignal(kind="supabase.rls_or_migration", value="present", path=relative_path))

    for env_match in ENV_PATTERN.findall(content):
        signals.append(ContextCodeSignal(kind="supabase.env_var", value=env_match, path=relative_path))

    return signals


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _dedupe_signals(signals: list[ContextCodeSignal]) -> list[ContextCodeSignal]:
    deduped: list[ContextCodeSignal] = []
    seen: set[tuple[str, str, str]] = set()
    for signal in signals:
        key = (signal.kind, signal.value, signal.path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(signal)
    return deduped
