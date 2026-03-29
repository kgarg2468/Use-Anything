#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
usage: install_use_anything.sh [-global]

Installs Use-Anything command packs and wrapper.
Default mode installs into the current project directory.
Pass -global to install into your home directory.
USAGE
}

MODE="local"
TARGET_ROOT="$PWD"

if [[ $# -gt 1 ]]; then
  usage
  exit 2
fi

if [[ $# -eq 1 ]]; then
  case "$1" in
    -global)
      MODE="global"
      TARGET_ROOT="${HOME}"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage
      exit 2
      ;;
  esac
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"${SCRIPT_DIR}/install_command_packs.sh" "${TARGET_ROOT}"

WRAPPER_PATH="${TARGET_ROOT}/.local/bin/use-anything-command"
WRAPPER_PATH_ESCAPED="${WRAPPER_PATH//&/\\&}"
INSTALLER_HINT="bash /path/to/Use-Anything/scripts/install_use_anything.sh"
INSTALLER_HINT_ESCAPED="${INSTALLER_HINT//&/\\&}"

rewrite_command_pack() {
  local file="$1"
  local tmp_file
  tmp_file="$(mktemp)"
  sed \
    -e "s|use-anything-command|${WRAPPER_PATH_ESCAPED}|g" \
    -e "s|bash ./scripts/install_command_packs.sh|${INSTALLER_HINT_ESCAPED}|g" \
    "${file}" >"${tmp_file}"
  mv "${tmp_file}" "${file}"
}

rewrite_command_pack "${TARGET_ROOT}/.claude/commands/use-anything.md"
rewrite_command_pack "${TARGET_ROOT}/.codex/prompts/use-anything.md"
rewrite_command_pack "${TARGET_ROOT}/.config/opencode/commands/use-anything.md"

cat <<MSG

install_use_anything complete
mode: ${MODE}
install_root: ${TARGET_ROOT}

Use in terminal:
- use-anything <target>
- ${WRAPPER_PATH} <target>

Use in Claude/Codex:
- /use-anything <target>
MSG
