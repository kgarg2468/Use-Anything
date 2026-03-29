from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INSTALLER_PATH = PROJECT_ROOT / "scripts" / "install_use_anything.sh"


def _run_installer(args: list[str], *, env: dict[str, str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(INSTALLER_PATH), *args],
        cwd=cwd or PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def test_installer_script_exists_and_is_executable() -> None:
    assert INSTALLER_PATH.exists()
    assert os.access(INSTALLER_PATH, os.X_OK)


def test_help_mentions_orchestrator_flags() -> None:
    result = subprocess.run(
        [str(INSTALLER_PATH), "--help"],
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": "/usr/bin:/bin"},
    )

    assert result.returncode == 0
    assert "--platform" in result.stdout
    assert "--source" in result.stdout
    assert "--project-dir" in result.stdout
    assert "--dry-run" in result.stdout
    assert "--check" in result.stdout


def test_install_all_platforms_repo_source(tmp_path: Path) -> None:
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # Precreate typo alias to ensure cleanup happens.
    alias_path = project_dir / ".claude" / "commands" / "useantyhig.md"
    alias_path.parent.mkdir(parents=True, exist_ok=True)
    alias_path.write_text("legacy alias", encoding="utf-8")

    # Precreate legacy command files to ensure cleanup across platforms.
    (home_dir / ".codex" / "prompts").mkdir(parents=True, exist_ok=True)
    (home_dir / ".claude" / "commands").mkdir(parents=True, exist_ok=True)
    (home_dir / ".config" / "opencode" / "commands").mkdir(parents=True, exist_ok=True)
    (home_dir / ".codex" / "prompts" / "use-anything.md").write_text("legacy", encoding="utf-8")
    (home_dir / ".claude" / "commands" / "use-anything.md").write_text("legacy", encoding="utf-8")
    (home_dir / ".config" / "opencode" / "commands" / "use-anything.md").write_text("legacy", encoding="utf-8")

    env = {
        "HOME": str(home_dir),
        "CODEX_HOME": str(codex_home),
        "PATH": "/usr/bin:/bin",
    }
    args = ["--platform", "all", "--source", "repo", "--project-dir", str(project_dir)]

    first = _run_installer(args, env=env)
    second = _run_installer(args, env=env)

    assert first.returncode == 0
    assert second.returncode == 0

    codex_skill_dir = codex_home / "skills" / "use-anything"
    assert (codex_skill_dir / "SKILL.md").exists()
    assert (codex_skill_dir / "agents" / "openai.yaml").exists()
    assert (codex_skill_dir / "references" / "commands.md").exists()

    claude_commands = project_dir / ".claude" / "commands"
    assert (claude_commands / "use-anything.md").exists()
    assert not (claude_commands / "useantyhig.md").exists()

    assert (home_dir / ".config" / "opencode" / "commands" / "use-anything.md").exists()
    assert (home_dir / ".openclaw" / "skills" / "use-anything" / "SKILL.md").exists()
    assert (home_dir / ".config" / "qoder" / "commands" / "use-anything.md").exists()
    assert (home_dir / ".config" / "copilot" / "commands" / "use-anything.md").exists()

    qoder_registry = home_dir / ".qoder.json"
    assert qoder_registry.exists()
    registry_payload = json.loads(qoder_registry.read_text(encoding="utf-8"))
    assert any(entry.get("name") == "use-anything" for entry in registry_payload.get("commands", []))

    assert not (home_dir / ".codex" / "prompts" / "use-anything.md").exists()
    assert not (home_dir / ".claude" / "commands" / "use-anything.md").exists()


def test_install_single_platform_codex_only(tmp_path: Path) -> None:
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()

    result = _run_installer(
        ["--platform", "codex", "--source", "package"],
        env={
            "HOME": str(home_dir),
            "CODEX_HOME": str(codex_home),
            "PATH": "/usr/bin:/bin",
        },
    )

    assert result.returncode == 0
    assert (codex_home / "skills" / "use-anything" / "SKILL.md").exists()
    assert not (home_dir / ".config" / "qoder" / "commands" / "use-anything.md").exists()


def test_dry_run_does_not_mutate_filesystem(tmp_path: Path) -> None:
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    result = _run_installer(
        ["--platform", "all", "--project-dir", str(project_dir), "--dry-run"],
        env={
            "HOME": str(home_dir),
            "CODEX_HOME": str(codex_home),
            "PATH": "/usr/bin:/bin",
        },
    )

    assert result.returncode == 0
    assert "DRY-RUN" in result.stdout
    assert not (codex_home / "skills" / "use-anything" / "SKILL.md").exists()
    assert not (project_dir / ".claude" / "commands" / "use-anything.md").exists()


def test_check_mode_validates_without_installing(tmp_path: Path) -> None:
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()

    result = _run_installer(
        ["--platform", "codex", "--check"],
        env={
            "HOME": str(home_dir),
            "CODEX_HOME": str(codex_home),
            "PATH": "/usr/bin:/bin",
        },
    )

    assert result.returncode == 0
    assert "CHECK OK" in result.stdout
    assert not (codex_home / "skills" / "use-anything").exists()


def test_unknown_platform_exits_non_zero(tmp_path: Path) -> None:
    home_dir = tmp_path / "home"
    home_dir.mkdir()

    result = _run_installer(
        ["--platform", "wat"],
        env={
            "HOME": str(home_dir),
            "PATH": "/usr/bin:/bin",
        },
    )

    assert result.returncode != 0
    assert "unknown --platform" in result.stderr
