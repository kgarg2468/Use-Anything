#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: use-anything-command <target-or-url> [extra args]" >&2
  exit 2
fi

if command -v uv >/dev/null 2>&1; then
  CMD=(uv run use-anything "$@")
elif command -v use-anything >/dev/null 2>&1; then
  CMD=(use-anything "$@")
else
  echo "use-anything-command: neither 'uv' nor 'use-anything' is available on PATH" >&2
  exit 127
fi

if [[ "${USE_ANYTHING_WRAPPER_DRY_RUN:-0}" == "1" ]]; then
  printf 'DRY_RUN:'
  for token in "${CMD[@]}"; do
    printf ' %q' "$token"
  done
  printf '\n'
  exit 0
fi

exec "${CMD[@]}"
