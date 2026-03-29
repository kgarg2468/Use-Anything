"""Lightweight guardrail for accidentally tracked generated artifacts."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

FORBIDDEN_SNIPPETS = (
    "__pycache__/",
    ".pytest_cache/",
    ".ruff_cache/",
    ".mypy_cache/",
    "dist/",
    "build/",
)


def main() -> int:
    result = subprocess.run(
        ["git", "ls-files"],
        check=True,
        text=True,
        capture_output=True,
    )
    tracked_files = [line.strip() for line in result.stdout.splitlines() if line.strip()]

    violations: list[str] = []
    for path in tracked_files:
        if not Path(path).exists():
            continue
        if any(snippet in path for snippet in FORBIDDEN_SNIPPETS):
            violations.append(path)
            continue
        if ".egg-info/" in path or path.endswith(".egg-info"):
            violations.append(path)
            continue
        if path == ".coverage" or path.startswith(".coverage."):
            violations.append(path)

    if not violations:
        print("Repo hygiene check passed.")
        return 0

    print("Repo hygiene check found tracked generated artifacts:")
    for path in violations:
        print(f"- {path}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
