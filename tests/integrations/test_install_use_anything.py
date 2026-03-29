from __future__ import annotations

import os
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INSTALLER_PATH = PROJECT_ROOT / "scripts" / "install_use_anything.sh"


def test_installer_script_exists_and_is_executable() -> None:
    assert INSTALLER_PATH.exists()
    assert os.access(INSTALLER_PATH, os.X_OK)


def test_local_install_by_default(tmp_path: Path) -> None:
    project_dir = tmp_path / "optX"
    project_dir.mkdir()
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()

    (home_dir / ".codex" / "prompts").mkdir(parents=True, exist_ok=True)
    (home_dir / ".claude" / "commands").mkdir(parents=True, exist_ok=True)
    (home_dir / ".config" / "opencode" / "commands").mkdir(parents=True, exist_ok=True)
    (home_dir / ".codex" / "prompts" / "use-anything.md").write_text("legacy", encoding="utf-8")
    (home_dir / ".claude" / "commands" / "use-anything.md").write_text("legacy", encoding="utf-8")
    (home_dir / ".config" / "opencode" / "commands" / "use-anything.md").write_text("legacy", encoding="utf-8")

    result = subprocess.run(
        [str(INSTALLER_PATH)],
        cwd=project_dir,
        capture_output=True,
        text=True,
        check=False,
        env={
            "HOME": str(home_dir),
            "CODEX_HOME": str(codex_home),
            "PATH": "/usr/bin:/bin",
        },
    )

    assert result.returncode == 0
    assert (codex_home / "skills" / "use-anything" / "SKILL.md").exists()
    assert (codex_home / "skills" / "use-anything" / "agents" / "openai.yaml").exists()
    assert not (home_dir / ".codex" / "prompts" / "use-anything.md").exists()
    assert not (home_dir / ".claude" / "commands" / "use-anything.md").exists()
    assert not (home_dir / ".config" / "opencode" / "commands" / "use-anything.md").exists()
    assert "Installed skill:" in result.stdout
    assert "Invoke with: $use-anything" in result.stdout


def test_global_install_with_flag(tmp_path: Path) -> None:
    project_dir = tmp_path / "optX"
    project_dir.mkdir()
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    codex_home = home_dir / ".codex"

    result = subprocess.run(
        [str(INSTALLER_PATH), "-global"],
        cwd=project_dir,
        capture_output=True,
        text=True,
        check=False,
        env={
            "HOME": str(home_dir),
            "PATH": "/usr/bin:/bin",
        },
    )

    assert result.returncode == 0
    assert (codex_home / "skills" / "use-anything" / "SKILL.md").exists()
    assert (codex_home / "skills" / "use-anything" / "references" / "commands.md").exists()
    assert "Installed skill:" in result.stdout
    assert str(codex_home / "skills" / "use-anything") in result.stdout


def test_unknown_flag_exits_non_zero(tmp_path: Path) -> None:
    project_dir = tmp_path / "optX"
    project_dir.mkdir()

    result = subprocess.run(
        [str(INSTALLER_PATH), "--wat"],
        cwd=project_dir,
        capture_output=True,
        text=True,
        check=False,
        env={
            "HOME": str(tmp_path / "home"),
            "PATH": "/usr/bin:/bin",
        },
    )

    assert result.returncode != 0
    assert "usage:" in result.stderr.lower()
