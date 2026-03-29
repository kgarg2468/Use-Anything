#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
usage: install_use_anything.sh [-global]

Install the `use-anything` Codex skill into $CODEX_HOME/skills (defaults to ~/.codex/skills).
The optional -global flag is accepted for compatibility and installs to the same destination.
USAGE
}

if [[ $# -gt 1 ]]; then
  usage
  exit 2
fi

if [[ $# -eq 1 ]]; then
  case "$1" in
    -global)
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

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_SKILL_DIR="${REPO_ROOT}/skills/use-anything"

if [[ ! -f "${SOURCE_SKILL_DIR}/SKILL.md" ]]; then
  echo "install_use_anything: missing source skill at ${SOURCE_SKILL_DIR}" >&2
  exit 1
fi

CODEX_HOME_DIR="${CODEX_HOME:-${HOME}/.codex}"
DEST_SKILLS_DIR="${CODEX_HOME_DIR}/skills"
DEST_SKILL_DIR="${DEST_SKILLS_DIR}/use-anything"

mkdir -p "${DEST_SKILLS_DIR}"
rm -rf "${DEST_SKILL_DIR}"
cp -R "${SOURCE_SKILL_DIR}" "${DEST_SKILL_DIR}"

# Remove legacy prompt-command integration files for this project.
rm -f "${HOME}/.codex/prompts/use-anything.md"
rm -f "${HOME}/.claude/commands/use-anything.md"
rm -f "${HOME}/.config/opencode/commands/use-anything.md"

cat <<MSG
Installed skill:
- Name: use-anything
- Path: ${DEST_SKILL_DIR}

Use in Codex:
- Invoke with: \$use-anything

Use in terminal:
- use-anything <target>

Install via skill-installer (alternative):
- \$skill-installer install https://github.com/kgarg2468/Use-Anything/tree/main/skills/use-anything

Restart Codex to pick up new skills.
MSG
