# Use-Anything

Use-Anything generates agent-optimized `SKILL.md` directories from existing software interfaces.

## Current scope

This phase supports multiple input target types:

- PyPI package names (for example `requests`)
- GitHub repository URLs (for example `https://github.com/pallets/flask`)
- Documentation URLs (for example `https://docs.stripe.com`)
- Local source directories (for example `./my-project`)
- Binaries via `--binary` (for example `--binary ffmpeg`)

Supported commands:

- `use-anything <target>`
- `use-anything --binary <name>`
- `use-anything probe <target>`
- `use-anything probe --binary <name>`
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

# Full pipeline from docs URL
uv run use-anything https://docs.python-requests.org/en/latest/

# Full pipeline from GitHub repository
uv run use-anything https://github.com/pallets/flask

# Full pipeline from local directory
uv run use-anything ./my-project

# Full pipeline from binary
uv run use-anything --binary ffmpeg

# Force full regeneration (skip merge from discovered existing skill)
uv run use-anything requests --force

# Full pipeline via Codex CLI backend
uv run use-anything requests --model codex-cli

# Probe only
uv run use-anything requests --probe-only

# Explicit probe command
uv run use-anything probe requests

# Validate generated output
uv run use-anything validate ./use-anything-requests
```

## Enhancement behavior

When probing discovers an upstream `SKILL.md`, Use-Anything enhances output by:

- Regenerating canonical sections (`Setup`, `Key concepts`, workflows, constraints, quick reference).
- Preserving non-canonical custom sections from the upstream skill.
- Preserving unknown metadata keys in frontmatter.

Use `--force` to bypass this merge behavior and fully regenerate canonical output.

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
