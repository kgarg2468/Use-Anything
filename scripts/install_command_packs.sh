#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_HOME="${1:-$HOME}"
LOCAL_BIN_DIR="${TARGET_HOME}/.local/bin"

install_file() {
  local src="$1"
  local dst="$2"
  mkdir -p "$(dirname "${dst}")"
  cp "${src}" "${dst}"
}

install_file "${REPO_ROOT}/integrations/claude-code/.claude/commands/use-anything.md" "${TARGET_HOME}/.claude/commands/use-anything.md"
install_file "${REPO_ROOT}/integrations/codex/.codex/prompts/use-anything.md" "${TARGET_HOME}/.codex/prompts/use-anything.md"
install_file "${REPO_ROOT}/integrations/opencode/commands/use-anything.md" "${TARGET_HOME}/.config/opencode/commands/use-anything.md"

mkdir -p "${LOCAL_BIN_DIR}"
cp "${REPO_ROOT}/scripts/use_anything_command.sh" "${LOCAL_BIN_DIR}/use-anything-command"
chmod +x "${LOCAL_BIN_DIR}/use-anything-command"

cat <<MSG
Installed command packs:
- Claude Code: ${TARGET_HOME}/.claude/commands/use-anything.md
- Codex: ${TARGET_HOME}/.codex/prompts/use-anything.md
- OpenCode: ${TARGET_HOME}/.config/opencode/commands/use-anything.md
- Wrapper: ${LOCAL_BIN_DIR}/use-anything-command

Ensure ${LOCAL_BIN_DIR} is on your PATH before invoking commands.
MSG
