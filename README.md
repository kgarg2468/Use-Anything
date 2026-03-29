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

## Codex Skill Install

Use-Anything is distributed as a Codex skill (`$use-anything`), not a slash prompt command.

Install method 1 (Codex-native, via skill installer):

```text
$skill-installer install https://github.com/kgarg2468/Use-Anything/tree/main/skills/use-anything
```

Install method 2 (shell script):

```bash
bash /path/to/Use-Anything/scripts/install_use_anything.sh
```

Both methods install to `$CODEX_HOME/skills/use-anything` (defaults to `~/.codex/skills/use-anything`).

After install, restart Codex so `$use-anything` is discovered.

Integration details:

- [Codex Skill Integration](docs/platform-integrations.md#codex-skill)

## Claude Code (Single Project)

Install project-local Claude commands from your target project directory:

```bash
bash /path/to/Use-Anything/scripts/install_claude_project_command.sh
```

This writes:
- `.claude/commands/use-anything.md`
- `.claude/commands/useantyhig.md` (alias)

Then restart Claude Code in that project and use:
- `/use-anything <target>`
- `/useantyhig <target>`

## Usage

```bash
# Use from Codex skill context:
$use-anything

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
bash ./scripts/install_use_anything.sh
```

If you installed from a released package name:

```bash
uv tool upgrade use-anything
bash ./scripts/install_use_anything.sh
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
