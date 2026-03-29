from __future__ import annotations

import os
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INSTALLER_PATH = PROJECT_ROOT / "scripts" / "install_claude_project_command.sh"


def test_claude_installer_script_exists_and_is_executable() -> None:
    assert INSTALLER_PATH.exists()
    assert os.access(INSTALLER_PATH, os.X_OK)


def test_installs_project_local_claude_commands(tmp_path: Path) -> None:
    project_dir = tmp_path / "optX"
    project_dir.mkdir()

    result = subprocess.run(
        [str(INSTALLER_PATH)],
        cwd=project_dir,
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": "/usr/bin:/bin"},
    )

    assert result.returncode == 0
    use_anything = project_dir / ".claude" / "commands" / "use-anything.md"
    useantyhig = project_dir / ".claude" / "commands" / "useantyhig.md"
    assert use_anything.exists()
    assert useantyhig.exists()

    content = use_anything.read_text(encoding="utf-8")
    alias_content = useantyhig.read_text(encoding="utf-8")
    assert "use-anything $ARGUMENTS" in content
    assert content == alias_content
    assert "Installed Claude project commands:" in result.stdout


def test_unknown_flag_exits_non_zero(tmp_path: Path) -> None:
    project_dir = tmp_path / "optX"
    project_dir.mkdir()

    result = subprocess.run(
        [str(INSTALLER_PATH), "--wat"],
        cwd=project_dir,
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": "/usr/bin:/bin"},
    )

    assert result.returncode != 0
    assert "usage:" in result.stderr.lower()
