#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
usage: install_claude_project_command.sh [project-dir]

Install project-local Claude command files for Use-Anything:
- /use-anything
- /useantyhig (alias)
USAGE
}

if [[ $# -gt 1 ]]; then
  usage
  exit 2
fi

if [[ $# -eq 1 && ( "$1" == "-h" || "$1" == "--help" ) ]]; then
  usage
  exit 0
fi

if [[ $# -eq 1 && "$1" == -* ]]; then
  usage
  exit 2
fi

PROJECT_DIR="${1:-$PWD}"
if [[ ! -d "${PROJECT_DIR}" ]]; then
  echo "install_claude_project_command: project directory not found: ${PROJECT_DIR}" >&2
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_CMD="${REPO_ROOT}/integrations/claude-code/.claude/commands/use-anything.md"

if [[ ! -f "${SOURCE_CMD}" ]]; then
  echo "install_claude_project_command: missing template: ${SOURCE_CMD}" >&2
  exit 1
fi

TARGET_DIR="${PROJECT_DIR}/.claude/commands"
mkdir -p "${TARGET_DIR}"
cp "${SOURCE_CMD}" "${TARGET_DIR}/use-anything.md"
cp "${SOURCE_CMD}" "${TARGET_DIR}/useantyhig.md"

cat <<MSG
Installed Claude project commands:
- ${TARGET_DIR}/use-anything.md
- ${TARGET_DIR}/useantyhig.md

Use in Claude Code:
- /use-anything <target>
- /useantyhig <target>

Restart Claude Code in this project if commands were already open.
MSG
