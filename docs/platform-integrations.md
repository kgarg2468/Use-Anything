# Platform Integrations

Use-Anything provides a unified installer for platform adapters:

```bash
bash ./scripts/install_use_anything.sh --platform <platform> --source <repo|package> [--project-dir <path>]
```

## Installer options

- `--platform codex|claude|opencode|openclaw|qoder|copilot|all`
- `--source repo|package`
- `--project-dir <path>` (required for a non-current Claude project)
- `--dry-run`
- `--check`

## Platform table

| Platform | Install command | Installed location | Invoke |
|---|---|---|---|
| Codex | `--platform codex` | `$CODEX_HOME/skills/use-anything` | `$use-anything` |
| Claude Code | `--platform claude --project-dir <dir>` | `<dir>/.claude/commands/use-anything.md` | `/use-anything <target>` |
| OpenCode | `--platform opencode` | `~/.config/opencode/commands/use-anything.md` | `/use-anything <target>` |
| OpenClaw | `--platform openclaw` | `~/.openclaw/skills/use-anything/SKILL.md` | `@use-anything` |
| Qoder | `--platform qoder` | `~/.config/qoder/commands/use-anything.md` + `~/.qoder.json` | `/use-anything <target>` |
| Copilot CLI | `--platform copilot` | `~/.config/copilot/commands/use-anything.md` | `/use-anything <target>` |

## Quick commands

Install all adapters in one run:

```bash
bash ./scripts/install_use_anything.sh --platform all --source repo --project-dir "$PWD"
```

Claude-only convenience wrapper:

```bash
bash ./scripts/install_claude_project_command.sh /absolute/path/to/project
```

## Verify installation

```bash
# Validate adapter sources and configuration
bash ./scripts/install_use_anything.sh --platform all --check

# Confirm CLI and first run
use-anything --help
use-anything run requests --probe-only
```

## Troubleshooting

- Use `--dry-run` to see file operations before writing anything.
- If `--check` fails, ensure all adapter templates exist under `integrations/`.
- If commands are missing in your agent UI, restart the host process after install.
- For Claude, ensure `--project-dir` points at the project where you run Claude Code.

## Legacy cleanup behavior

The installer removes legacy prompt-command artifacts:
- `~/.codex/prompts/use-anything.md`
- `~/.claude/commands/use-anything.md`

It also removes the old typo alias from project-local Claude installs:
- `<project>/.claude/commands/useantyhig.md`

## Integration tests

```bash
uv run pytest -q \
  tests/integrations/test_install_use_anything.py \
  tests/integrations/test_install_claude_project_command.py \
  tests/integrations/test_command_packs.py \
  tests/integrations/test_docs_install_onboarding.py
```
