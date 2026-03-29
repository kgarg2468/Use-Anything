from __future__ import annotations

import os
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WRAPPER_PATH = PROJECT_ROOT / "scripts" / "use_anything_command.sh"


def test_platform_adapter_assets_exist() -> None:
    assert (PROJECT_ROOT / "integrations" / "claude-code" / ".claude" / "commands" / "use-anything.md").exists()
    assert (PROJECT_ROOT / "integrations" / "opencode" / "commands" / "use-anything.md").exists()
    assert (PROJECT_ROOT / "integrations" / "openclaw" / "skills" / "use-anything" / "SKILL.md").exists()
    assert (PROJECT_ROOT / "integrations" / "qoder" / "commands" / "use-anything.md").exists()
    assert (PROJECT_ROOT / "integrations" / "copilot" / "commands" / "use-anything.md").exists()
    assert not (PROJECT_ROOT / "integrations" / "codex" / ".codex" / "prompts" / "use-anything.md").exists()


def test_wrapper_is_executable() -> None:
    assert WRAPPER_PATH.exists()
    assert os.access(WRAPPER_PATH, os.X_OK)


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def test_wrapper_prefers_uv_in_dry_run(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_executable(bin_dir / "uv", "#!/usr/bin/env bash\nexit 0\n")

    result = subprocess.run(
        [str(WRAPPER_PATH), "requests", "--probe-only"],
        capture_output=True,
        text=True,
        check=False,
        env={
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "USE_ANYTHING_WRAPPER_DRY_RUN": "1",
        },
    )

    assert result.returncode == 0
    assert "DRY_RUN:" in result.stdout
    assert "uv" in result.stdout
    assert "use-anything" in result.stdout
    assert "requests" in result.stdout


def test_wrapper_falls_back_to_use_anything_in_dry_run(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_executable(bin_dir / "use-anything", "#!/usr/bin/env bash\nexit 0\n")

    result = subprocess.run(
        [str(WRAPPER_PATH), "requests"],
        capture_output=True,
        text=True,
        check=False,
        env={
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "USE_ANYTHING_WRAPPER_DRY_RUN": "1",
        },
    )

    assert result.returncode == 0
    assert "DRY_RUN:" in result.stdout
    assert "use-anything" in result.stdout


def test_wrapper_errors_when_no_runner_available(tmp_path: Path) -> None:
    empty_bin = tmp_path / "empty"
    empty_bin.mkdir()

    result = subprocess.run(
        [str(WRAPPER_PATH), "requests"],
        capture_output=True,
        text=True,
        check=False,
        env={
            "PATH": f"{empty_bin}:/usr/bin:/bin",
        },
    )

    assert result.returncode == 127
    assert "neither 'uv' nor 'use-anything'" in result.stderr
