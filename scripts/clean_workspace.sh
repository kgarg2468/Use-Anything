#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

echo "Cleaning transient workspace artifacts (preserving .venv)..."

rm -rf \
  .pytest_cache \
  .ruff_cache \
  .mypy_cache \
  .coverage \
  .coverage.* \
  dist \
  build

# Remove bytecode caches and files outside .venv.
find . -path "./.venv" -prune -o -type d -name "__pycache__" -exec rm -rf {} +
find . -path "./.venv" -prune -o -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete

echo "Workspace cleanup complete."
