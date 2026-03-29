#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
usage: install_use_anything.sh --platform <codex|claude|opencode|openclaw|qoder|copilot|all> [options]

Install Use-Anything adapter assets for one or more supported platforms.

Options:
  --platform <name>      Target platform (required)
  --source <repo|package>  Distribution channel hint (default: repo)
  --project-dir <path>   Claude project directory (default: current directory)
  --dry-run              Print planned actions without mutating filesystem
  --check                Validate source assets and config without installing
  -global                Compatibility alias for: --platform codex
  -h, --help             Show this help message
USAGE
}

log() {
  echo "$*"
}

die() {
  echo "$*" >&2
  exit 2
}

DRY_RUN=0
CHECK_ONLY=0
PLATFORM=""
SOURCE="repo"
PROJECT_DIR="$PWD"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --platform)
      [[ $# -ge 2 ]] || die "missing value for --platform"
      PLATFORM="$2"
      shift 2
      ;;
    --source)
      [[ $# -ge 2 ]] || die "missing value for --source"
      SOURCE="$2"
      shift 2
      ;;
    --project-dir)
      [[ $# -ge 2 ]] || die "missing value for --project-dir"
      PROJECT_DIR="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --check)
      CHECK_ONLY=1
      shift
      ;;
    -global)
      PLATFORM="codex"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      die "unknown argument: $1"
      ;;
  esac
done

if [[ -z "$PLATFORM" ]]; then
  usage >&2
  die "--platform is required"
fi

if [[ "$SOURCE" != "repo" && "$SOURCE" != "package" ]]; then
  usage >&2
  die "unknown --source: $SOURCE"
fi

case "$PLATFORM" in
  codex|claude|opencode|openclaw|qoder|copilot|all)
    ;;
  *)
    usage >&2
    die "unknown --platform: $PLATFORM"
    ;;
esac

if [[ ! -d "$PROJECT_DIR" ]]; then
  die "project directory not found: $PROJECT_DIR"
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_DIR="${HOME:-$(eval echo ~)}"

CODEX_SOURCE_DIR="${REPO_ROOT}/skills/use-anything"
CLAUDE_TEMPLATE="${REPO_ROOT}/integrations/claude-code/.claude/commands/use-anything.md"
OPENCODE_TEMPLATE="${REPO_ROOT}/integrations/opencode/commands/use-anything.md"
OPENCLAW_TEMPLATE="${REPO_ROOT}/integrations/openclaw/skills/use-anything/SKILL.md"
QODER_TEMPLATE="${REPO_ROOT}/integrations/qoder/commands/use-anything.md"
COPILOT_TEMPLATE="${REPO_ROOT}/integrations/copilot/commands/use-anything.md"

CODEX_HOME_DIR="${CODEX_HOME:-${HOME_DIR}/.codex}"

run_cmd() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf 'DRY-RUN:'
    for token in "$@"; do
      printf ' %q' "$token"
    done
    printf '\n'
    return 0
  fi
  "$@"
}

copy_file() {
  local src="$1"
  local dst="$2"
  run_cmd mkdir -p "$(dirname "$dst")"
  run_cmd cp "$src" "$dst"
}

copy_dir() {
  local src="$1"
  local dst="$2"
  run_cmd mkdir -p "$(dirname "$dst")"
  run_cmd rm -rf "$dst"
  run_cmd cp -R "$src" "$dst"
}

remove_file() {
  local path="$1"
  run_cmd rm -f "$path"
}

check_source_file() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    echo "CHECK FAILED: missing source file: $path" >&2
    exit 1
  fi
}

check_source_dir() {
  local path="$1"
  if [[ ! -d "$path" ]]; then
    echo "CHECK FAILED: missing source directory: $path" >&2
    exit 1
  fi
}

check_platform() {
  local platform="$1"
  case "$platform" in
    codex)
      check_source_dir "$CODEX_SOURCE_DIR"
      check_source_file "$CODEX_SOURCE_DIR/SKILL.md"
      ;;
    claude)
      check_source_file "$CLAUDE_TEMPLATE"
      ;;
    opencode)
      check_source_file "$OPENCODE_TEMPLATE"
      ;;
    openclaw)
      check_source_file "$OPENCLAW_TEMPLATE"
      ;;
    qoder)
      check_source_file "$QODER_TEMPLATE"
      ;;
    copilot)
      check_source_file "$COPILOT_TEMPLATE"
      ;;
  esac
  echo "CHECK OK: ${platform}"
}

install_codex() {
  local dest_skill_dir="${CODEX_HOME_DIR}/skills/use-anything"
  copy_dir "$CODEX_SOURCE_DIR" "$dest_skill_dir"
  log "Installed codex skill -> ${dest_skill_dir}"
}

install_claude() {
  local target_dir="${PROJECT_DIR}/.claude/commands"
  copy_file "$CLAUDE_TEMPLATE" "${target_dir}/use-anything.md"
  remove_file "${target_dir}/useantyhig.md"
  log "Installed claude command -> ${target_dir}/use-anything.md"
}

install_opencode() {
  local target_file="${HOME_DIR}/.config/opencode/commands/use-anything.md"
  copy_file "$OPENCODE_TEMPLATE" "$target_file"
  log "Installed opencode command -> ${target_file}"
}

install_openclaw() {
  local target_file="${HOME_DIR}/.openclaw/skills/use-anything/SKILL.md"
  copy_file "$OPENCLAW_TEMPLATE" "$target_file"
  log "Installed openclaw skill -> ${target_file}"
}

install_qoder() {
  local command_file="${HOME_DIR}/.config/qoder/commands/use-anything.md"
  local registry_file="${HOME_DIR}/.qoder.json"
  copy_file "$QODER_TEMPLATE" "$command_file"
  if [[ "$DRY_RUN" == "1" ]]; then
    log "DRY-RUN: would update qoder registry -> ${registry_file}"
  else
    cat >"$registry_file" <<JSON
{
  "commands": [
    {
      "name": "use-anything",
      "path": "$command_file",
      "invoke": "/use-anything"
    }
  ]
}
JSON
  fi
  log "Installed qoder command -> ${command_file}"
}

install_copilot() {
  local target_file="${HOME_DIR}/.config/copilot/commands/use-anything.md"
  copy_file "$COPILOT_TEMPLATE" "$target_file"
  log "Installed copilot command -> ${target_file}"
}

cleanup_legacy() {
  remove_file "${HOME_DIR}/.codex/prompts/use-anything.md"
  remove_file "${HOME_DIR}/.claude/commands/use-anything.md"
}

platforms=()
if [[ "$PLATFORM" == "all" ]]; then
  platforms=(codex claude opencode openclaw qoder copilot)
else
  platforms=("$PLATFORM")
fi

if [[ "$CHECK_ONLY" == "1" ]]; then
  for platform in "${platforms[@]}"; do
    check_platform "$platform"
  done
  log "CHECK OK: source=${SOURCE}"
  exit 0
fi

log "Install channel: ${SOURCE}"
for platform in "${platforms[@]}"; do
  check_platform "$platform"
  "install_${platform}"
done
cleanup_legacy

cat <<MSG

Installation complete.
- Platforms: ${platforms[*]}
- Source: ${SOURCE}
- Claude project dir: ${PROJECT_DIR}

Verify:
- use-anything --help
- use-anything run requests --probe-only
MSG
