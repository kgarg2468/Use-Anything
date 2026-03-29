#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
usage: install_claude_project_command.sh [project-dir]

Install project-local Claude command file for Use-Anything:
- /use-anything
USAGE
}

if [[ $# -gt 1 ]]; then
  usage >&2
  exit 2
fi

if [[ $# -eq 1 && ( "$1" == "-h" || "$1" == "--help" ) ]]; then
  usage
  exit 0
fi

if [[ $# -eq 1 && "$1" == -* ]]; then
  usage >&2
  exit 2
fi

PROJECT_DIR="${1:-$PWD}"
if [[ ! -d "${PROJECT_DIR}" ]]; then
  echo "install_claude_project_command: project directory not found: ${PROJECT_DIR}" >&2
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ORCHESTRATOR="${REPO_ROOT}/scripts/install_use_anything.sh"

if [[ ! -x "${ORCHESTRATOR}" ]]; then
  echo "install_claude_project_command: missing installer: ${ORCHESTRATOR}" >&2
  exit 1
fi

"${ORCHESTRATOR}" --platform claude --source repo --project-dir "${PROJECT_DIR}"

cat <<MSG
Installed Claude project commands:
- ${PROJECT_DIR}/.claude/commands/use-anything.md

Use in Claude Code:
- /use-anything <target>
MSG
