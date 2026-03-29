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

    result = subprocess.run(
        [str(INSTALLER_PATH)],
        cwd=project_dir,
        capture_output=True,
        text=True,
        check=False,
        env={
            "HOME": str(tmp_path / "home"),
            "PATH": "/usr/bin:/bin",
        },
    )

    assert result.returncode == 0
    assert (project_dir / ".claude" / "commands" / "use-anything.md").exists()
    assert (project_dir / ".codex" / "prompts" / "use-anything.md").exists()
    assert (project_dir / ".local" / "bin" / "use-anything-command").exists()
    claude_cmd = (project_dir / ".claude" / "commands" / "use-anything.md").read_text(encoding="utf-8")
    codex_cmd = (project_dir / ".codex" / "prompts" / "use-anything.md").read_text(encoding="utf-8")
    expected_wrapper = str(project_dir / ".local" / "bin" / "use-anything-command")
    assert expected_wrapper in claude_cmd
    assert expected_wrapper in codex_cmd
    assert "mode: local" in result.stdout


def test_global_install_with_flag(tmp_path: Path) -> None:
    project_dir = tmp_path / "optX"
    project_dir.mkdir()
    home_dir = tmp_path / "home"
    home_dir.mkdir()

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
    assert (home_dir / ".claude" / "commands" / "use-anything.md").exists()
    assert (home_dir / ".codex" / "prompts" / "use-anything.md").exists()
    assert (home_dir / ".local" / "bin" / "use-anything-command").exists()
    claude_cmd = (home_dir / ".claude" / "commands" / "use-anything.md").read_text(encoding="utf-8")
    codex_cmd = (home_dir / ".codex" / "prompts" / "use-anything.md").read_text(encoding="utf-8")
    expected_wrapper = str(home_dir / ".local" / "bin" / "use-anything-command")
    assert expected_wrapper in claude_cmd
    assert expected_wrapper in codex_cmd
    assert "mode: global" in result.stdout


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
