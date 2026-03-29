# Platform Command Packs

Use-Anything ships repo-native command packs for Claude Code, Codex, and OpenCode. All three delegate to one shared wrapper: `use-anything-command`.

## Install

From the repository root:

```bash
bash ./scripts/install_command_packs.sh
```

This installs:

- `~/.claude/commands/use-anything.md`
- `~/.codex/prompts/use-anything.md`
- `~/.config/opencode/commands/use-anything.md`
- `~/.local/bin/use-anything-command`

Ensure `~/.local/bin` is on your `PATH`.

## Wrapper Behavior

`use-anything-command` runs:

1. `uv run use-anything <args>` when `uv` is available
2. `use-anything <args>` when `uv` is unavailable but the binary exists
3. exits `127` when neither runner is installed

Dry-run mode for verification:

```bash
USE_ANYTHING_WRAPPER_DRY_RUN=1 use-anything-command requests --probe-only
```

## Quick Verification Matrix

| Platform | Installed file | Expected invocation |
|---|---|---|
| Claude Code | `~/.claude/commands/use-anything.md` | `use-anything-command $ARGUMENTS` |
| Codex | `~/.codex/prompts/use-anything.md` | `use-anything-command {{args}}` |
| OpenCode | `~/.config/opencode/commands/use-anything.md` | `use-anything-command $ARGUMENTS` |

## Deterministic Contract Test

```bash
uv run pytest -q tests/integrations/test_command_packs.py
```
