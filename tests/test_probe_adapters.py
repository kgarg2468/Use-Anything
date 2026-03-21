from __future__ import annotations

import subprocess
from pathlib import Path

import httpx
import pytest

import use_anything.probe.adapters as adapters
from use_anything.probe.adapters import (
    _fetch_github_tree,
    _fetch_url,
    _merge_docs_candidates,
    _parse_github_owner_repo,
    _parse_openapi_document,
    _verify_existing_skill_endpoint,
    _verify_llms_endpoint,
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


@pytest.mark.fault_injection
def test_probe_binary_handles_timeout_and_keeps_cli_fallback(monkeypatch) -> None:
    def fake_run(*args, **kwargs):  # noqa: ANN002, ANN003
        raise subprocess.TimeoutExpired(cmd="demo --help", timeout=2)

    monkeypatch.setattr(adapters.subprocess, "run", fake_run)
    candidates, metadata = probe_binary("demo")

    assert any(candidate.type == "cli_tool" for candidate in candidates)
    assert metadata["command_output"]["help"] == ""
    assert metadata["command_output"]["version"] == ""


def test_probe_local_directory_detects_python_sdk(tmp_path: Path) -> None:
    project_dir = tmp_path / "sample"
    project_dir.mkdir()
    (project_dir / "pyproject.toml").write_text("[project]\nname='sample'\n")

    candidates, metadata = probe_local_directory(project_dir)

    assert any(candidate.type == "python_sdk" for candidate in candidates)
    assert metadata["path"] == str(project_dir)


def test_probe_local_directory_handles_relative_errors_and_scan_cap(monkeypatch) -> None:
    class FakeFile:
        def __init__(self, index: int) -> None:
            self.index = index

        def is_file(self) -> bool:
            return True

        def relative_to(self, directory):  # noqa: ANN001, ARG002
            raise ValueError("outside root")

        def __str__(self) -> str:
            return f"/tmp/f{self.index}.py"

    class FakeDirectory:
        def rglob(self, pattern: str):  # noqa: ARG002
            return [FakeFile(index) for index in range(1200)]

        def __str__(self) -> str:
            return "/tmp/project"

    monkeypatch.setattr(
        adapters,
        "discover_interface_candidates",
        lambda **kwargs: [
            adapters.InterfaceCandidate(
                type="python_sdk",
                location="local",
                quality_score=0.6,
                coverage="partial",
                notes="x",
            )
        ],
    )

    candidates, metadata = probe_local_directory(FakeDirectory())  # type: ignore[arg-type]

    assert candidates
    assert metadata["files_scanned"] == 1000


def test_probe_docs_url_requires_verified_preflight_content(monkeypatch) -> None:
    monkeypatch.setattr(adapters, "_fetch_url", lambda url, timeout=15.0: (404, "text/plain", ""))

    candidates, metadata = probe_docs_url("https://docs.example.dev", html="<html><body>No links</body></html>")

    types = {candidate.type for candidate in candidates}
    assert "openapi_spec" not in types
    assert "llms_txt" not in types
    assert "existing_skill" not in types
    assert "rest_api_docs" in types
    assert metadata["url"] == "https://docs.example.dev"


def test_probe_docs_url_verifies_openapi_llms_and_existing_skill(monkeypatch) -> None:
    responses = {
        "https://docs.example.dev/openapi.json": (
            200,
            "application/json",
            '{"openapi":"3.0.0","paths":{"/users":{"get":{}}}}',
        ),
        "https://docs.example.dev/llms.txt": (
            200,
            "text/plain",
            "Use this documentation for API workflows.",
        ),
        "https://docs.example.dev/.well-known/skills/default/skill.md": (
            200,
            "text/markdown",
            "---\nname: demo\ndescription: test\n---\n\n# demo",
        ),
    }

    monkeypatch.setattr(
        adapters,
        "_fetch_url",
        lambda url, timeout=15.0: responses.get(url, (404, "text/plain", "")),
    )

    candidates, metadata = probe_docs_url("https://docs.example.dev", html="<html><body>No links</body></html>")

    types = {candidate.type for candidate in candidates}
    assert "openapi_spec" in types
    assert "llms_txt" in types
    assert "existing_skill" in types
    openapi = next(candidate for candidate in candidates if candidate.type == "openapi_spec")
    assert openapi.metadata["verified"] is True
    assert openapi.metadata["verification_method"] == "http_probe"
    assert metadata["verified_interface_types"] == ["existing_skill", "llms_txt", "openapi_spec"]


@pytest.mark.fault_injection
def test_fetch_url_returns_empty_payload_on_http_timeout(monkeypatch) -> None:
    def fake_get(url: str, timeout: float = 15.0):  # noqa: ARG001
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(adapters.httpx, "get", fake_get)
    status_code, content_type, payload = _fetch_url("https://docs.example.dev/openapi.json")

    assert status_code == 0
    assert content_type == ""
    assert payload == ""


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


def test_fetch_github_tree_uses_default_branch_when_available(monkeypatch) -> None:
    class FakeResponse:
        def __init__(self, status_code: int, payload: dict) -> None:
            self.status_code = status_code
            self._payload = payload

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                request = httpx.Request("GET", "https://api.github.com")
                response = httpx.Response(self.status_code, request=request)
                raise httpx.HTTPStatusError("boom", request=request, response=response)

        def json(self) -> dict:
            return self._payload

    def fake_get(url: str, timeout: float = 20.0):  # noqa: ARG001
        if url == "https://api.github.com/repos/example/project":
            return FakeResponse(200, {"default_branch": "stable"})
        if url == "https://api.github.com/repos/example/project/git/trees/stable?recursive=1":
            return FakeResponse(200, {"tree": [{"path": "pyproject.toml"}, {"path": "README.md"}]})
        return FakeResponse(404, {})

    monkeypatch.setattr(adapters.httpx, "get", fake_get)

    payload = _fetch_github_tree("https://github.com/example/project")

    assert payload["default_branch"] == "stable"
    assert payload["resolved_ref"] == "stable"
    assert payload["tree_paths"] == ["pyproject.toml", "README.md"]


@pytest.mark.fault_injection
def test_fetch_github_tree_falls_back_when_primary_ref_is_rate_limited(monkeypatch) -> None:
    class FakeResponse:
        def __init__(self, status_code: int, payload: dict) -> None:
            self.status_code = status_code
            self._payload = payload

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                request = httpx.Request("GET", "https://api.github.com")
                response = httpx.Response(self.status_code, request=request)
                raise httpx.HTTPStatusError("boom", request=request, response=response)

        def json(self) -> dict:
            return self._payload

    def fake_get(url: str, timeout: float = 20.0):  # noqa: ARG001
        if url == "https://api.github.com/repos/example/project":
            return FakeResponse(200, {"default_branch": "main"})
        if url == "https://api.github.com/repos/example/project/git/trees/main?recursive=1":
            return FakeResponse(429, {})
        if url == "https://api.github.com/repos/example/project/git/trees/master?recursive=1":
            return FakeResponse(200, {"tree": [{"path": "README.md"}]})
        return FakeResponse(404, {})

    monkeypatch.setattr(adapters.httpx, "get", fake_get)

    payload = _fetch_github_tree("https://github.com/example/project")

    assert payload["default_branch"] == "main"
    assert payload["resolved_ref"] == "master"
    assert payload["tree_paths"] == ["README.md"]


def test_fetch_github_tree_returns_empty_payload_when_refs_fail(monkeypatch) -> None:
    class FakeResponse:
        def __init__(self, status_code: int, payload: dict) -> None:
            self.status_code = status_code
            self._payload = payload

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                request = httpx.Request("GET", "https://api.github.com")
                response = httpx.Response(self.status_code, request=request)
                raise httpx.HTTPStatusError("boom", request=request, response=response)

        def json(self) -> dict:
            return self._payload

    def fake_get(url: str, timeout: float = 20.0):  # noqa: ARG001
        if url == "https://api.github.com/repos/example/project":
            return FakeResponse(500, {})
        return FakeResponse(500, {})

    monkeypatch.setattr(adapters.httpx, "get", fake_get)
    payload = _fetch_github_tree("https://github.com/example/project")

    assert payload == {"tree_paths": [], "default_branch": "", "resolved_ref": ""}


def test_parse_github_owner_repo_normalizes_tree_and_blob_paths() -> None:
    assert _parse_github_owner_repo("https://github.com/example/project/tree/main") == ("example", "project")
    assert _parse_github_owner_repo("https://github.com/example/project/blob/main/README.md") == (
        "example",
        "project",
    )


def test_parse_github_owner_repo_rejects_unsupported_suffixes() -> None:
    assert _parse_github_owner_repo("https://github.com/example/project/issues/1") == ("", "")


def test_verify_llms_and_existing_skill_reject_invalid_payloads(monkeypatch) -> None:
    monkeypatch.setattr(
        adapters,
        "_fetch_url",
        lambda url: (200, "text/html", "<html>not llms content</html>"),
    )
    assert _verify_llms_endpoint("https://docs.example.dev/llms.txt") is None

    monkeypatch.setattr(
        adapters,
        "_fetch_url",
        lambda url: (200, "text/plain", "just plain text without frontmatter"),
    )
    assert _verify_existing_skill_endpoint("https://docs.example.dev/skill.md") is None


def test_parse_openapi_document_and_merge_candidates_paths() -> None:
    assert _parse_openapi_document("not-json: [") == {}
    assert _parse_openapi_document("- just\n- a\n- list\n") == {}

    heuristic = [
        adapters.InterfaceCandidate(
            type="openapi_spec",
            location="https://docs.example/openapi.json",
            quality_score=0.5,
            coverage="partial",
            notes="heuristic",
        ),
        adapters.InterfaceCandidate(
            type="rest_api_docs",
            location="https://docs.example",
            quality_score=0.4,
            coverage="partial",
            notes="rest",
        ),
    ]
    verified = [
        adapters.InterfaceCandidate(
            type="openapi_spec",
            location="https://docs.example/openapi.json",
            quality_score=0.9,
            coverage="full",
            notes="verified",
        ),
    ]

    merged = _merge_docs_candidates(heuristic_candidates=heuristic, verified_candidates=verified)

    assert merged[0].notes == "verified"
    assert any(item.type == "rest_api_docs" for item in merged)
