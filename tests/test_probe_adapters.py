from __future__ import annotations

from pathlib import Path

from use_anything.probe.adapters import (
    probe_binary,
    probe_docs_url,
    probe_github_repo,
    probe_local_directory,
)


def test_probe_binary_returns_cli_candidate() -> None:
    candidates, metadata = probe_binary("ffmpeg", command_output={"help": "usage: ffmpeg", "version": "ffmpeg 7.1"})

    assert candidates
    assert candidates[0].type == "cli_tool"
    assert metadata["binary"] == "ffmpeg"


def test_probe_local_directory_detects_python_sdk(tmp_path: Path) -> None:
    project_dir = tmp_path / "sample"
    project_dir.mkdir()
    (project_dir / "pyproject.toml").write_text("[project]\nname='sample'\n")

    candidates, metadata = probe_local_directory(project_dir)

    assert any(candidate.type == "python_sdk" for candidate in candidates)
    assert metadata["path"] == str(project_dir)


def test_probe_docs_url_detects_openapi_and_llms() -> None:
    html = """
    <html>
      <body>
        <a href=\"/openapi.json\">OpenAPI</a>
        <a href=\"/llms.txt\">LLMS</a>
      </body>
    </html>
    """

    candidates, metadata = probe_docs_url("https://docs.example.dev", html=html)

    assert any(candidate.type == "openapi_spec" for candidate in candidates)
    assert any(candidate.type == "llms_txt" for candidate in candidates)
    assert metadata["url"] == "https://docs.example.dev"


def test_probe_github_repo_detects_existing_skill() -> None:
    payload = {
        "tree_paths": [
            "README.md",
            "docs/openapi.yaml",
            ".well-known/skills/default/skill.md",
        ]
    }

    candidates, metadata = probe_github_repo("https://github.com/example/project", tree_payload=payload)

    assert any(candidate.type == "openapi_spec" for candidate in candidates)
    assert any(candidate.type == "existing_skill" for candidate in candidates)
    assert metadata["repo_url"] == "https://github.com/example/project"
