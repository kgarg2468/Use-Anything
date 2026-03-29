# Platform Command Packs

Use-Anything ships repo-native command packs for Claude Code, Codex, and OpenCode.
All three delegate to one shared wrapper: `use-anything-command`.

## Prerequisite: Global CLI Install

Install `use-anything` globally first so commands work from any project directory.

```bash
# from this repository root
uv tool install --from . use-anything
```

Verify:

```bash
use-anything --help
```

## Install / Refresh Command Packs

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

With a global install, the wrapper fallback (`use-anything`) works in any cwd.

Dry-run mode for verification:

```bash
USE_ANYTHING_WRAPPER_DRY_RUN=1 use-anything-command requests --probe-only
```

## Claude Code

- Command file location: `~/.claude/commands/use-anything.md`
- Install/refresh: `bash ./scripts/install_command_packs.sh`
- Example invocation in Claude Code: `/use-anything requests`
- Verification:

```bash
USE_ANYTHING_WRAPPER_DRY_RUN=1 use-anything-command requests --probe-only
```

## Codex

- Command file location: `~/.codex/prompts/use-anything.md`
- Install/refresh: `bash ./scripts/install_command_packs.sh`
- Example invocation in Codex prompt/command flow: `use-anything-command requests --probe-only`
- Verification:

```bash
USE_ANYTHING_WRAPPER_DRY_RUN=1 use-anything-command requests --probe-only
```

## OpenCode

- Command file location: `~/.config/opencode/commands/use-anything.md`
- Install/refresh: `bash ./scripts/install_command_packs.sh`
- Example invocation in OpenCode: `/use-anything requests`
- Verification:

```bash
USE_ANYTHING_WRAPPER_DRY_RUN=1 use-anything-command requests --probe-only
```

## Update Flow

Repo-based install:

```bash
git pull
uv tool install --force --from . use-anything
bash ./scripts/install_command_packs.sh
```

Release-based install:

```bash
uv tool upgrade use-anything
bash ./scripts/install_command_packs.sh
```

## Deterministic Contract Test

```bash
uv run pytest -q tests/integrations/test_command_packs.py
```
