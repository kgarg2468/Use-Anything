# Use-Anything

Use-Anything generates agent-optimized `SKILL.md` directories from existing software interfaces.

## Current scope

Supported input targets:
- PyPI package names (for example `requests`)
- GitHub repository URLs (for example `https://github.com/pallets/flask`)
- Documentation URLs (for example `https://docs.stripe.com`)
- Local source directories (for example `./my-project`)
- Binaries via `--binary` (for example `--binary ffmpeg`)

Supported commands:
- `use-anything run <target>`
- `use-anything <target>` (implicit run)
- `use-anything --binary <name>`
- `use-anything probe <target>`
- `use-anything probe --binary <name>`
- `use-anything validate <skill_dir>`

## Platform Support Matrix

| Platform | Install via orchestrator | Invoke after install | Status |
|---|---|---|---|
| Codex | `--platform codex` | `$use-anything` | First-class |
| Claude Code | `--platform claude --project-dir <dir>` | `/use-anything <target>` | First-class |
| OpenCode | `--platform opencode` | `/use-anything <target>` | First-class |
| OpenClaw | `--platform openclaw` | `@use-anything` or native skill invocation | First-class |
| Qoder | `--platform qoder` | `/use-anything <target>` | First-class |
| Copilot CLI | `--platform copilot` | `/use-anything <target>` | First-class |

## Install Channels (Hybrid)

Both channels are supported:

1. Package channel:
```bash
uv tool install use-anything
```

2. Repo channel:
```bash
git clone https://github.com/kgarg2468/Use-Anything.git
cd Use-Anything
```

Install adapters with the orchestrator:
```bash
bash ./scripts/install_use_anything.sh --platform all --source repo --project-dir "$PWD"
```

The installer supports:
- `--platform codex|claude|opencode|openclaw|qoder|copilot|all`
- `--source repo|package`
- `--project-dir <path>`
- `--dry-run`
- `--check`

## 60-second quick start: Codex

```bash
# from repository root
bash ./scripts/install_use_anything.sh --platform codex --source repo
use-anything --help
```

Then in Codex:
```text
$use-anything
```

## 60-second quick start: Claude Code

```bash
# from repository root, target your Claude project directory
bash ./scripts/install_use_anything.sh --platform claude --source repo --project-dir /absolute/path/to/project
```

Then in Claude Code inside that project:
```text
/use-anything requests
```

## 60-second quick start: OpenCode

```bash
bash ./scripts/install_use_anything.sh --platform opencode --source repo
```

Then in OpenCode:
```text
/use-anything requests
```

## 60-second quick start: OpenClaw

```bash
bash ./scripts/install_use_anything.sh --platform openclaw --source repo
```

Then in OpenClaw:
```text
@use-anything requests
```

## 60-second quick start: Qoder

```bash
bash ./scripts/install_use_anything.sh --platform qoder --source repo
```

Then in Qoder:
```text
/use-anything requests
```

## 60-second quick start: Copilot CLI

```bash
bash ./scripts/install_use_anything.sh --platform copilot --source repo
```

Then in Copilot CLI:
```text
/use-anything requests
```

## Usage

```bash
# Explicit run command
use-anything run requests

# Implicit run command
use-anything requests

# Probe-only path
use-anything run requests --probe-only

# Full pipeline from docs URL
use-anything run https://docs.python-requests.org/en/latest/

# Full pipeline from repository URL
use-anything run https://github.com/pallets/flask

# Full pipeline from local directory
use-anything run ./my-project

# Full pipeline with explicit context docs
use-anything run ./my-project --context-doc /absolute/path/to/supabase.md

# Binary target
use-anything run --binary ffmpeg

# Regenerate canonical sections
use-anything run requests --force

# Probe command
use-anything probe requests

# Validate generated output
use-anything validate ./use-anything-requests
```

## Verify install

```bash
use-anything --help
use-anything run requests --probe-only
bash ./scripts/install_use_anything.sh --platform all --check
```

## Troubleshooting

- Use `--dry-run` to inspect planned actions:
  - `bash ./scripts/install_use_anything.sh --platform all --dry-run --project-dir "$PWD"`
- Use `--check` to validate source adapters exist before install.
- For Claude, confirm `--project-dir` points to the project where `.claude/commands/` should be created.
- Restart your agent host after installing adapters if commands/skills were already loaded.

## Integration details

- [Platform integrations](docs/platform-integrations.md)
- [Context-doc guardrails](docs/context-doc-guardrails.md)

## Development

```bash
make clean-workspace
make check-hygiene
uv run pytest -q
uv run ruff check .
```
