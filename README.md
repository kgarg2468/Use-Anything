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

## Global Install (Any Project)

Install the CLI globally so it works from any directory:

```bash
# from this repository root
uv tool install --from . use-anything
```

Fallback with `pipx`:

```bash
# from this repository root
pipx install .
```

Verify:

```bash
use-anything --help
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

## Provider Command Packs

Install the provider command packs (Claude Code, Codex, OpenCode).
Default installs into the current project directory. Use `-global` to install into home:

```bash
# from a project directory
bash /path/to/Use-Anything/scripts/install_use_anything.sh

# global install (~/.claude, ~/.codex, ~/.local/bin)
bash /path/to/Use-Anything/scripts/install_use_anything.sh -global
```

Local mode behavior:
- writes command packs/wrapper into the current project (`.claude`, `.codex`, `.config/opencode`, `.local/bin`)
- mirrors Claude/Codex command files to `~/.claude/commands` and `~/.codex/prompts` for CLI versions that only discover home-level slash commands
- keeps the command execution path project-scoped by embedding the project wrapper path in mirrored command files

After install, restart any open Codex/Claude session so `/use-anything` reloads.

Provider quick links:

- [Claude Code](docs/platform-integrations.md#claude-code)
- [Codex](docs/platform-integrations.md#codex)
- [OpenCode](docs/platform-integrations.md#opencode)

## Usage

```bash
# Full pipeline
use-anything requests

# Full pipeline from docs URL
use-anything https://docs.python-requests.org/en/latest/

# Full pipeline from GitHub repository
use-anything https://github.com/pallets/flask

# Full pipeline from local directory
use-anything ./my-project

# Full pipeline from binary
use-anything --binary ffmpeg

# Force full regeneration (skip merge from discovered existing skill)
use-anything requests --force

# Full pipeline via Codex CLI backend
use-anything requests --model codex-cli

# Probe only
use-anything requests --probe-only

# Explicit probe command
use-anything probe requests

# Validate generated output
use-anything validate ./use-anything-requests
```

## Updating

If you installed globally from this repository clone:

```bash
git pull
uv tool install --force --from . use-anything
bash ./scripts/install_use_anything.sh -global
```

If you installed from a released package name:

```bash
uv tool upgrade use-anything
bash ./scripts/install_use_anything.sh -global
```

## Enhancement behavior

When probing discovers an upstream `SKILL.md`, Use-Anything enhances output by:

- Regenerating canonical sections (`Setup`, `Key concepts`, workflows, constraints, quick reference).
- Preserving non-canonical custom sections from the upstream skill.
- Preserving unknown metadata keys in frontmatter.

Use `--force` to bypass this merge behavior and fully regenerate canonical output.

## Development

```bash
make clean-workspace
make check-hygiene
uv run pytest -q
uv run ruff check .
```
