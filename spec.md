# Use-Anything: Project Specification

## One-liner

Point Use-Anything at any software, and it generates agent-optimized skill files so AI agents can use that software directly — no wrapper code, no generated CLI, no intermediary.

---

## Problem Statement

AI agents (Claude Code, Codex, Gemini CLI, Cursor, etc.) are increasingly capable of using software programmatically — but only when they know *how*. The bottleneck is not the agent's ability to call functions; it's the agent's lack of knowledge about which functions exist, what they do, what order to call them in, and what will silently break.

Today, this knowledge gap is solved in two ways:

1. **Hand-authored skill files** — humans who've used the software write SKILL.md files manually. This works great but doesn't scale. Most software has zero skill coverage.
2. **Generated wrapper code** (e.g., CLI-Anything) — an LLM analyzes source code and generates a full CLI harness (thousands of lines of Python) that wraps the software. This is heavy: it requires installation, maintenance, testing, and the real software installed locally.

**Use-Anything takes a third path**: automatically analyze any software's existing interfaces (APIs, CLIs, SDKs, docs, config files) and generate agent-optimized SKILL.md files that teach agents how to use what's already there. Zero generated wrapper code. Zero installation. The agent reads the skill and drives the software directly.

---

## Core Philosophy

1. **Generate knowledge, not code.** The output is a SKILL.md skill file (and optional reference files), not a Python package or CLI binary.
2. **Use what exists.** If the software has a REST API, teach the agent to call it. If it has a Python SDK, teach the agent to import it. If it has a CLI, teach the agent to shell out. Never generate a new interface layer.
3. **Lightest viable path.** Always prefer the simplest interface that gives the agent adequate capability. A direct Python import beats shelling out to a CLI. A CLI beats screen-scraping.
4. **Agent Skills standard.** All output conforms to the open Agent Skills specification (agentskills.io/specification) so it works across Claude Code, Codex, Gemini CLI, Cursor, Kiro, VS Code Copilot, OpenCode, and any other skills-compatible agent.
5. **Compound, don't couple.** Each generated skill is standalone. No runtime dependencies on Use-Anything itself. The skill file is the entire deliverable.

---

## Architecture Overview

```
use-anything <target>
     |
     v
+--------------------------+
|  1. PROBE                |  Discover what interfaces the software exposes
|     - REST API / OpenAPI |
|     - Python SDK / PyPI  |
|     - CLI / man pages    |
|     - Node.js / npm      |
|     - D-Bus / IPC        |
|     - File formats       |
|     - Source code        |
|     - Documentation      |
+-----------+--------------+
            |
            v
+--------------------------+
|  2. RANK                 |  Score each interface on agent-usability
|     - Structured I/O?   |
|     - Error handling?    |
|     - Statefulness?      |
|     - Auth complexity?   |
|     - Documentation?     |
+-----------+--------------+
            |
            v
+--------------------------+
|  3. ANALYZE              |  Deep-read the best interface(s)
|     - Map capabilities   |
|     - Identify workflows |
|     - Find gotchas       |
|     - Extract examples   |
+-----------+--------------+
            |
            v
+--------------------------+
|  4. GENERATE             |  Produce the skill file(s)
|     - SKILL.md           |
|     - references/        |
|     - scripts/ (opt.)    |
|     - examples/ (opt.)   |
+-----------+--------------+
            |
            v
+--------------------------+
|  5. VALIDATE             |  Check quality and spec compliance
|     - Frontmatter valid  |
|     - Token budget met   |
|     - Workflows testable |
|     - Gotchas included   |
+--------------------------+
            |
            v
    Output: skill directory
    ready for any agent
```

---

## Phase 1: PROBE — Interface Discovery

The probe phase discovers what programmatic interfaces a piece of software exposes. It accepts multiple input types.

### Input Types

| Input | Example | What the prober does |
|-------|---------|---------------------|
| **URL (docs site)** | `https://docs.stripe.com` | Fetch llms.txt, skill.md, OpenAPI spec, sitemap. Crawl API reference pages. |
| **URL (GitHub repo)** | `https://github.com/blender/blender` | Clone shallow. Scan for setup.py/pyproject.toml (Python SDK), package.json (Node SDK), openapi.yaml, CLI entry points, README, /docs folder. |
| **Local directory** | `./my-project` | Same as repo scan but skip clone. |
| **Package name** | `stripe` or `npm:puppeteer` | Query PyPI/npm registry for metadata, then fetch docs URL, README, and API reference. |
| **Binary name** | `ffmpeg` | Run `<binary> --help`, `man <binary>`, check for `--version`, look for online docs. |

### What the prober looks for

For each target, probe for these interface types (in priority order):

```python
INTERFACE_TYPES = [
    {
        "type": "openapi_spec",
        "signals": ["openapi.yaml", "openapi.json", "swagger.json", "*.swagger.*"],
        "quality": "highest",  # Fully structured, typed, machine-readable
        "description": "OpenAPI/Swagger specification file"
    },
    {
        "type": "rest_api_docs",
        "signals": ["/api/", "/reference/", "REST API", "endpoints"],
        "quality": "high",
        "description": "REST API documentation pages"
    },
    {
        "type": "python_sdk",
        "signals": ["setup.py", "pyproject.toml", "pip install", "import X"],
        "quality": "high",
        "description": "Installable Python package with importable API"
    },
    {
        "type": "node_sdk",
        "signals": ["package.json", "npm install", "require()", "import from"],
        "quality": "high",
        "description": "Installable Node.js package"
    },
    {
        "type": "cli_tool",
        "signals": ["--help", "man page", "CLI reference", "console_scripts"],
        "quality": "medium",
        "description": "Command-line interface"
    },
    {
        "type": "graphql_api",
        "signals": ["schema.graphql", "/graphql", "query {", "mutation {"],
        "quality": "high",
        "description": "GraphQL API with schema"
    },
    {
        "type": "grpc_api",
        "signals": ["*.proto", "protobuf", "gRPC"],
        "quality": "high",
        "description": "gRPC service with protobuf definitions"
    },
    {
        "type": "file_format",
        "signals": ["*.odf", "*.svg", "*.mlt", "format specification"],
        "quality": "low",
        "description": "Documented file format the software reads/writes"
    },
    {
        "type": "plugin_api",
        "signals": ["Plugin API", "Extension API", "Script-Fu", "bpy", "AppleScript"],
        "quality": "medium-high",
        "description": "Scripting/plugin interface embedded in the software"
    },
    {
        "type": "llms_txt",
        "signals": ["llms.txt", "llms-full.txt", "/.well-known/"],
        "quality": "high",
        "description": "Existing LLM-optimized documentation"
    },
    {
        "type": "existing_skill",
        "signals": ["skill.md", "SKILL.md", "/.well-known/skills/"],
        "quality": "highest",
        "description": "Pre-existing agent skill file (enhance, don't replace)"
    }
]
```

### Probe output

```json
{
    "target": "stripe",
    "target_type": "pypi_package",
    "interfaces_found": [
        {
            "type": "openapi_spec",
            "location": "https://raw.githubusercontent.com/stripe/openapi/master/openapi/spec3.json",
            "quality_score": 0.95,
            "coverage": "full",
            "notes": "Complete OpenAPI 3.0 spec with all endpoints"
        },
        {
            "type": "python_sdk",
            "location": "pypi:stripe",
            "quality_score": 0.9,
            "coverage": "full",
            "notes": "Well-typed SDK, mirrors REST API 1:1"
        },
        {
            "type": "existing_skill",
            "location": "https://docs.stripe.com/.well-known/skills/default/skill.md",
            "quality_score": 0.7,
            "coverage": "partial",
            "notes": "Exists but may be incomplete — enhance rather than replace"
        }
    ],
    "recommended_interface": "python_sdk",
    "reasoning": "Python SDK provides typed, importable API. Agent can call stripe.Customer.create() directly. Preferred over raw REST for reduced boilerplate."
}
```

---

## Phase 2: RANK — Interface Scoring

Each discovered interface is scored on agent-usability.

### Scoring Criteria

| Criterion | Weight | Description |
|-----------|--------|-------------|
| **Structured I/O** | 25% | Does the interface accept/return structured data (typed params, JSON responses)? Or does it require string construction and output parsing? |
| **Error quality** | 15% | Are errors structured with codes and messages? Or just stderr strings? |
| **Statefulness** | 15% | Is it stateless (REST calls) or does it require session management? Stateless is better for agents. |
| **Auth complexity** | 10% | API key (simple) vs OAuth flow (complex) vs no auth (simplest). |
| **Documentation depth** | 20% | How well-documented is the interface? Does it have examples, type signatures, edge case notes? |
| **Ecosystem adoption** | 15% | Is this the interface most developers actually use? Community examples and Stack Overflow answers mean the LLM's training data has seen it before. |

### Ranking output

The ranker selects one primary interface and optionally a secondary interface. The primary is what the skill will teach; the secondary is mentioned as a fallback.

```json
{
    "primary": {
        "type": "python_sdk",
        "score": 0.92,
        "reasoning": "Typed SDK, stateless calls, simple API key auth, extensive docs, widely used in training data."
    },
    "secondary": {
        "type": "cli_tool",
        "score": 0.65,
        "reasoning": "CLI exists but requires string construction and stdout parsing. Useful as fallback if SDK isn't installed."
    },
    "rejected": [
        {
            "type": "file_format",
            "score": 0.25,
            "reasoning": "Raw file manipulation is fragile and the SDK handles this transparently."
        }
    ]
}
```

---

## Phase 3: ANALYZE — Deep Interface Analysis

Once the best interface is selected, the analyzer does a deep read to extract everything an agent needs to know.

### What the analyzer extracts

1. **Capability map**: What can this software do? Group by domain (e.g., for Stripe: Payments, Customers, Subscriptions, Invoices). For each capability, identify the specific function/endpoint/command.

2. **Core workflows**: The 5-15 most common multi-step tasks. Not just "here's every endpoint" but "here's how you charge a customer" as a sequence of calls. This is the critical difference between documentation and a skill — skills are procedural.

3. **Gotchas and edge cases**: What will silently break? What are the non-obvious constraints? What errors does every beginner hit? Sources: GitHub issues, Stack Overflow, changelog breaking changes, the software's own "common mistakes" docs.

4. **Authentication/setup**: What does the agent need before it can start? API keys, environment variables, package installation, config files.

5. **Output format patterns**: What does the software return? JSON objects, binary files, streams? How should the agent parse responses?

6. **Rate limits and constraints**: Anything that would cause the agent to fail at scale — rate limits, pagination, file size limits, timeouts.

### Analyzer sources (in priority order)

1. The interface itself (OpenAPI spec, SDK type signatures, --help output)
2. Official documentation (API reference, guides, tutorials)
3. llms.txt / llms-full.txt if available
4. Existing skill.md if available (treat as a starting point to improve)
5. README and CHANGELOG
6. GitHub Issues (filtered for common problems)
7. Source code (as a last resort for undocumented behavior)

### Analyzer output

A structured intermediate representation (not the final skill file) containing:

```json
{
    "software": "stripe",
    "interface": "python_sdk",
    "version": "latest",
    "setup": {
        "install": "pip install stripe",
        "auth": "stripe.api_key = os.environ['STRIPE_API_KEY']",
        "env_vars": ["STRIPE_API_KEY"],
        "prerequisites": ["Python 3.7+"]
    },
    "capability_groups": [
        {
            "name": "Payments",
            "capabilities": [
                {
                    "name": "Create a payment intent",
                    "function": "stripe.PaymentIntent.create(amount=, currency=, ...)",
                    "params": {},
                    "returns": "PaymentIntent object",
                    "notes": "Amount is in cents, not dollars. currency must be lowercase ISO 4217."
                }
            ]
        }
    ],
    "workflows": [
        {
            "name": "Charge a customer with a saved card",
            "steps": [
                "1. Retrieve customer: stripe.Customer.retrieve(customer_id)",
                "2. List payment methods: stripe.PaymentMethod.list(customer=customer_id, type='card')",
                "3. Create payment intent: stripe.PaymentIntent.create(amount=, currency=, customer=, payment_method=, confirm=True)",
                "4. Check status: intent.status should be 'succeeded'"
            ],
            "common_errors": [
                "Forgetting confirm=True — creates the intent but doesn't charge",
                "Amount in dollars instead of cents — $10 should be amount=1000"
            ]
        }
    ],
    "gotchas": [
        "All monetary amounts are in the smallest currency unit (cents for USD)",
        "API keys starting with sk_test_ hit the test environment",
        "List endpoints return paginated results — use auto_paging_iter() to get all",
        "Webhook signatures must be verified with stripe.Webhook.construct_event()"
    ]
}
```

---

## Phase 4: GENERATE — Skill File Production

The generator takes the analyzer output and produces a complete skill directory conforming to the Agent Skills specification.

### Output structure

```
use-anything-stripe/
├── SKILL.md                    # Main skill file (< 500 lines, < 5000 tokens)
├── references/
│   ├── API_REFERENCE.md        # Full capability map (loaded on demand)
│   ├── WORKFLOWS.md            # Detailed multi-step workflows
│   └── GOTCHAS.md              # Edge cases and common mistakes
├── scripts/                    # Optional: deterministic helpers
│   └── verify_setup.py         # Quick check that auth/install is working
└── examples/
    └── common_tasks.md         # Copy-pasteable code examples
```

### SKILL.md format

The main SKILL.md file must follow this structure:

```markdown
---
name: <software-name>
description: >
  <1-2 sentences: what this skill does and when to trigger it.
  Include specific keywords that match how users ask for this.
  Example: "Interact with the Stripe payments API using the Python SDK.
  Use when asked to process payments, manage customers, create subscriptions,
  handle invoices, or work with any Stripe functionality.">
license: MIT
metadata:
  author: use-anything
  version: "1.0"
  generated_by: use-anything
  source_interface: <python_sdk|rest_api|cli_tool|etc.>
  software_version: <version analyzed>
  generated_date: <ISO date>
---

# <Software Name>

<1-2 sentence overview of what the software does and which interface
this skill uses.>

## Setup

<Minimal setup required. Package install command, auth configuration,
env vars.>

## Key concepts

<3-5 bullet points: the mental model the agent needs. Core objects,
relationships, important terminology. Keep this very short — just
enough to orient.>

## Core workflows

<The 5-10 most important multi-step procedures. Each workflow is:
  - A task name
  - Numbered steps with actual code/commands
  - Expected output
  - One-line warning about the most common mistake>

## Important constraints

<Bullet list of gotchas, rate limits, non-obvious behaviors.
These are the things that prevent failures. This section is the
highest-value content in the entire skill file.>

## Quick reference

<Table or compact list of the most-used functions/endpoints/commands
with one-line descriptions. NOT an exhaustive API reference — that
goes in references/API_REFERENCE.md.>

## When to use references

<Tell the agent when to load additional reference files.
Example: "For the full API reference with all parameters, see
references/API_REFERENCE.md. For detailed workflow examples,
see references/WORKFLOWS.md.">
```

### Generation rules

1. **SKILL.md must be under 500 lines and under 5000 tokens.** This is loaded entirely into context on activation. Detailed reference material goes in references/ files.

2. **Workflows are procedural, not descriptive.** Write "1. Call X with params Y. 2. Check the response for Z." Not "The X endpoint accepts params Y and returns Z."

3. **Gotchas first, features second.** The content that prevents agent failures is more valuable than comprehensive feature coverage. A skill that covers 40% of the API but includes all the gotchas outperforms one that covers 100% of the API with no warnings.

4. **Code examples use the actual interface.** If the skill teaches the Python SDK, examples are Python. If it teaches a CLI, examples are shell commands. Never mix interfaces within a single workflow.

5. **No generated wrapper code in scripts/.** Scripts are only for deterministic helpers (setup verification, format conversion). The agent uses the software's native interface directly.

6. **Description field is critical for discovery.** It must include specific trigger phrases — the exact words a user would say when they want this skill. "Process payments" not "financial transaction management."

7. **Include version information.** The skill should note which version of the software/API it was analyzed against, so agents know if the skill might be stale.

---

## Phase 5: VALIDATE — Quality Checks

The validator runs a series of checks on the generated skill.

### Spec compliance checks

- SKILL.md exists with valid YAML frontmatter
- `name` field: lowercase, hyphens only, max 64 chars, no leading/trailing hyphens
- `description` field: max 1024 chars, includes trigger phrases
- SKILL.md body under 500 lines
- No XML angle brackets in frontmatter
- References use relative paths from skill root
- File structure matches Agent Skills specification

### Content quality checks

- Setup section includes install command and auth configuration
- At least 3 core workflows with numbered steps
- At least 5 gotchas/constraints listed
- All code examples are syntactically valid
- No placeholder text (TODO, TBD, insert here)
- Quick reference covers the 10 most-used operations
- Description includes at least 3 trigger phrases

### Token budget checks

- SKILL.md body under 5,000 tokens (hard limit)
- Individual reference files under 10,000 tokens each
- Total skill directory under 30,000 tokens

### Functional checks (optional, requires software access)

- Install command succeeds
- Auth verification script runs
- At least one workflow's first step executes without error

---

## CLI Interface

### Installation

```bash
# From PyPI (primary distribution)
pip install use-anything

# From source
git clone https://github.com/<org>/use-anything.git
cd use-anything
pip install -e .
```

### Commands

```bash
# Generate a skill from a PyPI package
use-anything stripe

# Generate from a GitHub repo
use-anything https://github.com/blender/blender

# Generate from a local directory
use-anything ./my-project

# Generate from a docs URL
use-anything https://docs.stripe.com

# Generate from a binary on PATH
use-anything --binary ffmpeg

# Specify output directory
use-anything stripe -o ./skills/stripe/

# Only run the probe phase (useful for debugging)
use-anything stripe --probe-only

# Force a specific interface type
use-anything stripe --interface python_sdk

# Use a specific LLM provider
use-anything stripe --model claude-sonnet-4-6
use-anything stripe --model gpt-4.1

# Validate an existing skill
use-anything validate ./skills/stripe/

# Update/refresh a skill (re-analyze, preserve manual edits)
use-anything update ./skills/stripe/

# List discovered interfaces without generating
use-anything probe stripe
```

### Output behavior

- Default output directory: `./use-anything-<name>/`
- If an existing skill.md is found at the target, Use-Anything enhances it rather than replacing it (unless `--force` is passed)
- All generated files include a comment noting they were generated by Use-Anything and the date
- The tool prints a summary on completion: interface used, token counts, number of workflows generated, validation result

---

## Technology Stack

### Language: Python 3.10+

The tool itself is a Python CLI. Rationale: widest distribution, access to PyPI inspection libraries, good HTTP/scraping ecosystem.

### Dependencies

```
# Core
click              # CLI framework
httpx              # HTTP client (async support)
pyyaml             # YAML parsing
tiktoken           # Token counting
rich               # Terminal output formatting

# Probing
requests           # Fallback HTTP
beautifulsoup4     # HTML parsing for docs crawling

# Analysis (LLM interaction)
anthropic          # Claude API client (primary)
openai             # OpenAI API client (secondary)

# Validation
jsonschema         # Spec validation
```

### LLM Usage

Use-Anything calls an LLM at two points:

1. **Phase 3 (Analyze)**: The LLM reads the raw interface documentation and extracts the structured intermediate representation (capabilities, workflows, gotchas). This is the heavy lift — it needs a model that can process large context and reason about software interfaces.

2. **Phase 4 (Generate)**: The LLM takes the structured IR and writes the final SKILL.md and reference files. This is a writing/formatting task.

Phases 1 (Probe), 2 (Rank), and 5 (Validate) are deterministic — no LLM needed.

**Default model**: Claude Sonnet (fast, capable, cost-effective for most targets). Users can override with `--model`.

**API key**: Read from `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` environment variable. The tool should prompt if neither is set.

---

## Project Structure

```
use-anything/
├── README.md
├── LICENSE                         # MIT
├── pyproject.toml                  # Package config
├── src/
│   └── use_anything/
│       ├── __init__.py
│       ├── __main__.py             # python -m use_anything
│       ├── cli.py                  # Click CLI entry point
│       ├── probe/
│       │   ├── __init__.py
│       │   ├── prober.py           # Main probe orchestrator
│       │   ├── pypi.py             # PyPI package prober
│       │   ├── npm.py              # npm package prober
│       │   ├── github.py           # GitHub repo prober
│       │   ├── docs_site.py        # Documentation site prober
│       │   ├── binary.py           # Local binary prober
│       │   └── local_dir.py        # Local directory prober
│       ├── rank/
│       │   ├── __init__.py
│       │   └── ranker.py           # Interface scoring
│       ├── analyze/
│       │   ├── __init__.py
│       │   ├── analyzer.py         # Main analysis orchestrator
│       │   ├── openapi.py          # OpenAPI spec analyzer
│       │   ├── python_sdk.py       # Python SDK analyzer
│       │   ├── cli_tool.py         # CLI tool analyzer
│       │   ├── rest_docs.py        # REST API docs analyzer
│       │   ├── node_sdk.py         # Node SDK analyzer
│       │   └── llm_client.py       # LLM interaction wrapper
│       ├── generate/
│       │   ├── __init__.py
│       │   ├── generator.py        # Main generation orchestrator
│       │   ├── skill_writer.py     # SKILL.md writer
│       │   ├── reference_writer.py # Reference file writer
│       │   └── templates/          # Jinja2 or string templates
│       │       ├── skill.md.j2
│       │       ├── api_reference.md.j2
│       │       └── workflows.md.j2
│       ├── validate/
│       │   ├── __init__.py
│       │   └── validator.py        # Spec and quality validation
│       └── utils/
│           ├── __init__.py
│           ├── http.py             # HTTP fetching utilities
│           ├── tokens.py           # Token counting
│           └── git.py              # Git clone/inspection
├── tests/
│   ├── test_probe/
│   ├── test_rank/
│   ├── test_analyze/
│   ├── test_generate/
│   ├── test_validate/
│   └── fixtures/                   # Sample OpenAPI specs, READMEs, etc.
└── examples/
    └── generated/                  # Example output for reference
        ├── use-anything-stripe/
        ├── use-anything-ffmpeg/
        └── use-anything-blender/
```

---

## Development Roadmap

### Phase 1: MVP (Build first)

**Goal**: Generate usable skills for Python packages with existing documentation.

1. Build the CLI skeleton (Click framework, basic argument parsing)
2. Implement the PyPI prober (fetch package metadata, README, docs URL)
3. Implement the ranker (simplified: prefer SDK > CLI > docs)
4. Implement the analyzer for Python SDKs (LLM reads docs + source, extracts IR)
5. Implement the skill writer (IR to SKILL.md + references/)
6. Implement the validator (spec compliance + token budget)
7. Test with 5 well-known packages: `stripe`, `requests`, `fastapi`, `boto3`, `openai`

**Success metric**: Generated skills for all 5 packages pass validation and are usable by Claude Code.

### Phase 2: Expand input types

8. GitHub repo prober
9. Docs site prober (crawl + extract)
10. Binary prober (--help, man pages)
11. OpenAPI spec analyzer (highest quality path)
12. CLI tool analyzer
13. llms.txt / existing skill.md detection and enhancement

### Phase 3: Quality and ecosystem

14. Improve gotcha extraction (mine GitHub Issues, Stack Overflow)
15. Functional validation (actually run setup + first workflow step)
16. Publish as a Claude Code plugin (slash command: `/use-anything <target>`)
17. Publish as an OpenCode command
18. Build a web interface for non-CLI users
19. Community skill registry (submit and share generated skills)

### Phase 4: The router (future)

20. Integrate with API-Anything (thin wrapper generation for poorly documented APIs)
21. Integrate with CLI-Anything (full harness generation for GUI-only software)
22. Build the router that auto-selects Use-Anything, API-Anything, or CLI-Anything based on probe results

---

## Key Design Decisions

### Why not just crawl docs and dump them into a skill file?

Raw documentation is written for humans, not agents. It's organized by feature, not by workflow. It includes marketing language, conceptual overviews, and navigation that wastes tokens. A skill file needs to be procedural — step 1, step 2, step 3 — and include the gotchas that docs often omit. The LLM analysis step transforms human docs into agent instructions.

### Why not generate MCP servers instead?

MCP servers are the right answer for runtime integration (live connections, streaming, auth management). But they require a running process, installation, and maintenance. Skill files are zero-overhead: a text file that loads on demand. For the vast majority of software, teaching the agent to use the existing interface via a skill file is sufficient and dramatically simpler. MCP server generation is a valid future extension (the "API-Anything" tier) but not the starting point.

### Why use an LLM for analysis instead of static parsing?

Static parsing (AST analysis, type extraction) works for well-structured Python SDKs but fails for CLI tools, REST APIs described in prose, undocumented behaviors, and cross-referencing between different doc pages. The LLM can read a CLI's --help output, a README, and a Stack Overflow thread about common mistakes, then synthesize all of that into a coherent skill file. The analysis quality ceiling is higher with an LLM, even though it costs API tokens.

### What about the SkillsBench finding that self-generated skills don't work?

The SkillsBench research tested agents writing skills about their own task performance — essentially introspection. Use-Anything is different: it's analyzing external software documentation and producing procedural instructions. The LLM isn't reflecting on its own behavior; it's reading an API reference and writing a cheat sheet. This is much closer to what LLMs are good at (summarization, extraction, technical writing) than self-improvement.

---

## Example Output

Here is what a generated skill would look like for `ffmpeg` (CLI tool):

```markdown
---
name: ffmpeg
description: >
  Use the ffmpeg command-line tool for audio/video processing.
  Trigger when asked to convert video formats, extract audio,
  trim/cut videos, merge clips, add subtitles, resize video,
  change framerate, compress video, create thumbnails, or
  any media processing task.
license: MIT
metadata:
  author: use-anything
  version: "1.0"
  generated_by: use-anything
  source_interface: cli_tool
  software_version: "7.1"
  generated_date: "2026-03-17"
---

# ffmpeg

Audio/video processing via the ffmpeg CLI. The agent should construct
ffmpeg commands and execute them via shell.

## Setup

ffmpeg must be installed on the system.

    # Check availability
    ffmpeg -version

    # macOS
    brew install ffmpeg

    # Ubuntu/Debian
    sudo apt install ffmpeg

## Key concepts

- ffmpeg processes media through a pipeline: input, decode, filter, encode, output
- `-i` specifies input files (can have multiple)
- Codec is selected with `-c:v` (video) and `-c:a` (audio)
- `-y` overwrites output without asking (always include for automation)
- Filter chains use `-vf` for video and `-af` for audio

## Core workflows

### Convert format

    ffmpeg -y -i input.mov -c:v libx264 -c:a aac output.mp4

### Extract audio from video

    ffmpeg -y -i input.mp4 -vn -c:a libmp3lame -q:a 2 output.mp3

`-vn` disables video stream. `-q:a 2` sets quality (0=best, 9=worst).

### Trim video by time

    ffmpeg -y -ss 00:01:30 -i input.mp4 -t 00:00:45 -c copy output.mp4

Place `-ss` BEFORE `-i` for fast seeking. `-t` is duration, not end time.
`-c copy` avoids re-encoding (fast but may have keyframe imprecision).

### Resize video

    ffmpeg -y -i input.mp4 -vf "scale=1280:720" -c:a copy output.mp4

Use `scale=-1:720` to auto-calculate width preserving aspect ratio.
The auto-calculated dimension must be divisible by 2 — use `scale=-2:720`.

### Create thumbnail from video

    ffmpeg -y -i input.mp4 -ss 00:00:05 -frames:v 1 thumbnail.jpg

## Important constraints

- Always use `-y` flag to overwrite outputs without prompting
- Place `-ss` before `-i` for fast input seeking (after `-i` is slow)
- `-t` is duration from seek point, NOT absolute end time. Use `-to` for absolute
- `scale=-1:N` can produce odd dimensions that break H.264. Use `-2:N` instead
- Audio codec `aac` requires `-strict experimental` on some older builds
- Concatenating files requires a text file listing inputs, not multiple `-i` flags
- Output format is inferred from extension — `.mp4` gets H.264+AAC by default
- Some containers don't support all codecs — `.webm` needs VP8/VP9 + Vorbis/Opus
- `-c copy` is fast but can't trim precisely (only on keyframes)

## Quick reference

| Task | Command pattern |
|------|----------------|
| Convert format | `ffmpeg -y -i in -c:v libx264 -c:a aac out.mp4` |
| Extract audio | `ffmpeg -y -i in -vn -c:a libmp3lame out.mp3` |
| Trim | `ffmpeg -y -ss START -i in -t DURATION -c copy out` |
| Resize | `ffmpeg -y -i in -vf "scale=W:H" out` |
| Thumbnail | `ffmpeg -y -i in -ss TIME -frames:v 1 out.jpg` |
| GIF | `ffmpeg -y -i in -vf "fps=10,scale=320:-2" out.gif` |
| Merge audio+video | `ffmpeg -y -i video -i audio -c copy out` |
| Add subtitles | `ffmpeg -y -i in -vf "subtitles=subs.srt" out` |
| Compress | `ffmpeg -y -i in -c:v libx264 -crf 28 out.mp4` |
| Get info | `ffprobe -v quiet -print_format json -show_streams in` |

## When to use references

For the complete filter reference and advanced encoding options,
see references/API_REFERENCE.md. For complex workflows like
batch processing and streaming, see references/WORKFLOWS.md.
```

---

## Testing Strategy

### Unit tests

- Probe: mock HTTP responses, verify interface detection for known package structures
- Rank: fixed inputs, verify scoring produces expected ordering
- Validate: sample skill files with known spec violations, verify all are caught

### Integration tests

- End-to-end: run `use-anything stripe --probe-only` and verify probe output structure
- End-to-end: run `use-anything requests` and verify a complete skill is generated that passes validation

### Quality tests (manual or LLM-judged)

- Generate skills for 10 popular packages
- Load each skill into Claude Code
- Ask Claude Code to perform 3 tasks using each skill
- Score: did the agent succeed? Did it hit any gotcha the skill should have warned about?

---

## Configuration

Use-Anything reads configuration from (in priority order):

1. CLI flags (`--model`, `--interface`, `-o`)
2. Environment variables (`USE_ANYTHING_MODEL`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`)
3. Config file (`~/.config/use-anything/config.yaml`)

```yaml
# ~/.config/use-anything/config.yaml
model: claude-sonnet-4-6
default_output_dir: ~/skills/
anthropic_api_key: sk-ant-...  # or use env var
```

---

## License

MIT — free to use, modify, and distribute.

---

*Use-Anything — teach any agent to use any software.*
