---
name: use-anything
description: Generate or refresh an agent skill from a software interface target. Use when a user wants to create SKILL.md content from a package, repo URL, docs URL, local directory, or binary, and run probe/validate/full pipeline commands.
---

# Use-Anything

Use the installed `use-anything` CLI directly from the terminal.

## Quick start

1. Confirm CLI is available: `use-anything --help`
2. Run full pipeline on a target:
   - `use-anything requests`
   - `use-anything https://github.com/pallets/flask`
   - `use-anything ./my-project`
   - `use-anything --binary ffmpeg`

## Common workflows

- Full pipeline with Codex CLI backend: `use-anything <target> --model codex-cli`
- Probe only: `use-anything <target> --probe-only`
- Explicit probe command: `use-anything probe <target>`
- Validate generated output: `use-anything validate <skill_dir>`
- Regenerate canonical sections: `use-anything <target> --force`

## Output conventions

- Default output directory: `./use-anything-<target-slug>`
- Main artifact: `SKILL.md`
- Optional references: `references/`

## Notes

- Prefer absolute paths for local project targets when the working directory may change.
- Restart Codex after installing this skill so `$use-anything` is discoverable.
