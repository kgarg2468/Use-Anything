# Use-Anything: Teach Any Agent to Use Any Software

> Point it at any software. Get a skill your agent can use immediately.

#### ⚡ Codex · ⚡ Claude Code · ⚡ OpenCode · ⚡ OpenClaw · ⚡ Qoder · ⚡ Copilot CLI

---

## 🤔 The Problem

AI agents are increasingly powerful — but they're blind to most software. They can reason about code, but they don't know the right order to call Stripe's API, the gotcha that breaks ffmpeg on Windows, or which of boto3's 500 methods are actually worth using.

The two existing solutions both fall short:
- **Hand-written skill files** — great quality, zero scale. Most software has no skill coverage.
- **Generated CLI wrappers** (like CLI-Anything) — powerful, but heavy. Installs new binaries, requires maintenance, needs the software locally.

**Use-Anything takes a third path**: analyze any software's *existing* interfaces (APIs, SDKs, CLIs, docs) and generate an agent-optimized `SKILL.md` that teaches agents to use what's already there.

Zero wrapper code. Zero new binaries. Just knowledge.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` set in your environment
- A supported agent: [Codex](#-codex) · [Claude Code](#-claude-code) · [OpenCode](#-opencode) · [OpenClaw](#-openclaw) · [Qoder](#-qoder) · [Copilot CLI](#-copilot-cli)

### Install

```bash
# Recommended: via uv
uv tool install use-anything

# Or: from source
git clone https://github.com/kgarg2468/Use-Anything.git
cd Use-Anything
pip install -e .
```

### Generate a skill in one command

```bash
# From a PyPI package
use-anything stripe

# From a GitHub repo
use-anything https://github.com/pallets/flask

# From a docs URL
use-anything https://docs.stripe.com

# From a local project
use-anything ./my-project

# From a binary on PATH
use-anything --binary ffmpeg
```

Output: a ready-to-use `use-anything-<name>/` skill directory with `SKILL.md` and reference files — drop it anywhere your agent looks for skills.

---

## 🎯 Pick Your Platform

### ⚡ Codex

```bash
# From repo root
bash ./scripts/install_use_anything.sh --platform codex --source repo
```

Then in Codex:
```
$use-anything stripe
```

---

### ⚡ Claude Code

```bash
# Installs a slash command into your Claude project
bash ./scripts/install_use_anything.sh --platform claude --source repo --project-dir /path/to/your/project
```

Then in Claude Code:
```
/use-anything stripe
```

---

### ⚡ OpenCode

```bash
bash ./scripts/install_use_anything.sh --platform opencode --source repo
```

Then in OpenCode:
```
/use-anything stripe
```

---

### ⚡ OpenClaw

```bash
bash ./scripts/install_use_anything.sh --platform openclaw --source repo
```

Then in OpenClaw:
```
@use-anything stripe
```

---

### ⚡ Qoder

```bash
bash ./scripts/install_use_anything.sh --platform qoder --source repo
```

Then in Qoder:
```
/use-anything stripe
```

---

### ⚡ Copilot CLI

```bash
bash ./scripts/install_use_anything.sh --platform copilot --source repo
```

Then in Copilot CLI:
```
/use-anything stripe
```

---

### Install all platforms at once

```bash
bash ./scripts/install_use_anything.sh --platform all --source repo --project-dir "$PWD"
```

The installer supports: `--platform codex|claude|opencode|openclaw|qoder|copilot|all` · `--source repo|package` · `--project-dir <path>` · `--dry-run` · `--check`

---

## ⚙️ How It Works

Use-Anything runs a fully automated 5-phase pipeline:

```
use-anything stripe
       |
       v
  1. PROBE      Discover what interfaces exist (REST API, Python SDK, CLI, OpenAPI spec, docs...)
       |
       v
  2. RANK       Score each interface on agent-usability (structure, error quality, auth complexity, docs depth)
       |
       v
  3. ANALYZE    Deep-read the best interface — extract capabilities, workflows, gotchas, edge cases
       |
       v
  4. GENERATE   Produce SKILL.md + reference files conforming to the Agent Skills spec
       |
       v
  5. VALIDATE   Check spec compliance, token budget, workflow completeness
       |
       v
  Output: use-anything-stripe/ skill directory
```

### What types of software can it handle?

| Input | Example |
|---|---|
| PyPI package | `use-anything stripe` |
| GitHub repo | `use-anything https://github.com/pallets/flask` |
| Docs URL | `use-anything https://docs.stripe.com` |
| Local directory | `use-anything ./my-project` |
| Binary on PATH | `use-anything --binary ffmpeg` |

### What interfaces does it detect?

OpenAPI specs · REST APIs · Python SDKs · Node.js SDKs · CLI tools · GraphQL APIs · gRPC services · Plugin/scripting APIs · `llms.txt` files · Existing `SKILL.md` files (enhances instead of replaces)

---

## 📦 What Gets Generated

```
use-anything-stripe/
├── SKILL.md                 # Main skill (< 500 lines, < 5000 tokens — loads into agent context)
├── references/
│   ├── API_REFERENCE.md     # Full capability map (loaded on demand)
│   ├── WORKFLOWS.md         # Detailed multi-step task walkthroughs
│   └── GOTCHAS.md           # Edge cases and common mistakes
├── scripts/
│   └── verify_setup.py      # Quick auth/install check
└── examples/
    └── common_tasks.md      # Copy-pasteable code examples
```

The `SKILL.md` is self-contained — no runtime dependency on Use-Anything. Drop it anywhere your agent framework looks for skills and it works immediately.

---

## 📋 Full Command Reference

```bash
# Generate (implicit run)
use-anything stripe
use-anything https://github.com/pallets/flask
use-anything https://docs.stripe.com
use-anything ./my-project
use-anything --binary ffmpeg

# Explicit run with options
use-anything run stripe                            # Full pipeline
use-anything run stripe --probe-only               # Probe only (no skill generated)
use-anything run stripe --force                    # Regenerate even if skill exists
use-anything run stripe --interface python_sdk     # Force a specific interface
use-anything run stripe --model claude-sonnet-4-6  # Use a specific LLM
use-anything run stripe -o ./skills/stripe/        # Custom output directory

# Other commands
use-anything probe stripe                          # Discover interfaces without generating
use-anything validate ./use-anything-stripe        # Validate an existing skill directory
```

---

## 🆚 Use-Anything vs CLI-Anything

| | Use-Anything | CLI-Anything |
|---|---|---|
| **Output** | `SKILL.md` knowledge file | Full Python CLI binary |
| **Approach** | Teaches agent to use *existing* interfaces | Generates a *new* CLI wrapper |
| **Weight** | Zero — one text file | Heavy — installs new package |
| **Best for** | APIs, SDKs, documented CLIs | GUI apps with no API |
| **Requires software locally** | No | Yes |
| **Maintenance** | Regenerate with `--force` | Tests + versioning |

They're designed to complement each other. Use-Anything is the first choice; CLI-Anything is for GUI-only software with no programmable interface.

---

## 📂 Project Structure

```
use-anything/
├── README.md
├── pyproject.toml
├── spec.md                          # Full design specification
├── src/use_anything/
│   ├── cli.py                       # Click CLI entry point
│   ├── probe/                       # Interface discovery (PyPI, GitHub, docs, binary, local)
│   ├── rank/                        # Interface scoring
│   ├── analyze/                     # Deep analysis (OpenAPI, Python SDK, CLI, REST docs)
│   ├── generate/                    # Skill file production + templates
│   └── validate/                    # Spec compliance + quality checks
├── integrations/
│   ├── claude-code/                 # Claude Code slash command adapter
│   ├── opencode/                    # OpenCode commands
│   ├── openclaw/                    # OpenClaw skill
│   ├── codex/                       # Codex skill
│   ├── qoder/                       # Qoder plugin
│   └── copilot/                     # Copilot CLI plugin
├── scripts/
│   └── install_use_anything.sh      # Universal installer (all platforms)
├── tests/
└── skills/                          # Example generated skills
```

---

## 🔍 Verify Your Install

```bash
use-anything --help
use-anything run requests --probe-only
bash ./scripts/install_use_anything.sh --platform all --check
```

---

## 🛠 Troubleshooting

| Problem | Fix |
|---|---|
| Commands not found after install | Restart your agent host — skills/commands are loaded at startup |
| `--project-dir` error (Claude Code) | Pass the absolute path to the project where `.claude/commands/` should live |
| Inspect what the installer will do | `bash ./scripts/install_use_anything.sh --platform all --dry-run --project-dir "$PWD"` |
| Check adapters exist before installing | Add `--check` flag |
| Skill references missing | Reference files in `references/` are loaded on demand — they don't need to be in the active context |

---

## 🗺 Roadmap

- [ ] Community skill registry — share and reuse generated skills
- [ ] Web interface for non-CLI users
- [ ] `use-anything update` — refresh a skill when the software updates
- [ ] Auto-router: detect when to use Use-Anything vs CLI-Anything vs raw MCP
- [ ] Support for closed-source software and web services
- [ ] Functional validation (actually run the first workflow step)

---

## 🤝 Contributing

Contributions welcome. See [spec.md](spec.md) for the full design specification — it covers the architecture, every pipeline phase, design decisions, and roadmap in detail.

```bash
# Dev setup
uv venv && uv sync --extra dev
uv run pytest -q
uv run ruff check .
```

---

## 📄 License

MIT
