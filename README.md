# Use-Anything

Use-Anything generates agent-optimized `SKILL.md` directories from existing software interfaces.

## MVP scope

This phase supports only **PyPI package names** as input targets.

Supported commands:

- `use-anything <target>`
- `use-anything probe <target>`
- `use-anything validate <skill_dir>`

## Setup

```bash
uv sync --extra dev
```

Set at least one API key for analysis/generation:

```bash
export ANTHROPIC_API_KEY=...
# or
export OPENAI_API_KEY=...
```

Or use local Codex CLI authentication (no API key env vars required by Use-Anything):

```bash
codex login
```

## Usage

```bash
# Full pipeline
uv run use-anything requests

# Full pipeline via Codex CLI backend
uv run use-anything requests --model codex-cli

# Probe only
uv run use-anything requests --probe-only

# Explicit probe command
uv run use-anything probe requests

# Validate generated output
uv run use-anything validate ./use-anything-requests
```

## Claude Code usage

After generation, copy or move output into Claude Code skills path, for example:

```bash
uv run use-anything requests -o ~/.claude/skills/requests
```

Then invoke by trigger phrase or slash command (if supported by skill naming).

## Development

```bash
uv run pytest -q
uv run ruff check .
```
