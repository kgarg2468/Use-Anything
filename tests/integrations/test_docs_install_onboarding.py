from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
README = PROJECT_ROOT / "README.md"
PLATFORM_DOC = PROJECT_ROOT / "docs" / "platform-integrations.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_readme_contains_platform_matrix_and_orchestrator_flags() -> None:
    text = _read(README)

    assert "Platform Support Matrix" in text
    assert "--platform" in text
    assert "--source" in text
    assert "--project-dir" in text


def test_readme_contains_per_platform_quickstarts() -> None:
    text = _read(README)

    assert "60-second quick start: Codex" in text
    assert "60-second quick start: Claude Code" in text
    assert "60-second quick start: OpenCode" in text
    assert "60-second quick start: OpenClaw" in text
    assert "60-second quick start: Qoder" in text
    assert "60-second quick start: Copilot CLI" in text


def test_platform_doc_includes_verify_and_troubleshoot_sections() -> None:
    text = _read(PLATFORM_DOC)

    assert "Verify installation" in text
    assert "Troubleshooting" in text
    assert "--dry-run" in text
    assert "--check" in text
