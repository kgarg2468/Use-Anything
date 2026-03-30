# Context-Doc Guardrails

Use context docs (for example `supabase.md`) as optional project hints during `use-anything run`.

## How to enable

```bash
use-anything run /absolute/path/to/project \
  --context-doc /absolute/path/to/supabase.md \
  --context-doc-max-tokens 800
```

- `--context-doc` is repeatable and opt-in only.
- `--context-doc-max-tokens` caps per-doc claims that can be injected.

## Frontmatter contract (optional but recommended)

```yaml
---
last_verified: 2026-03-29
scope: project_specific
owner: optx-platform
applies_to:
  - web
  - api
---
```

Fields:
- `last_verified`: ISO date (`YYYY-MM-DD`). Missing or stale docs are downgraded.
- `scope`: preferred values are `project_specific`, `mixed`, `generic`.
- `owner`: owning team/person.
- `applies_to`: string or list of strings for subsystem targeting.

## Precedence policy

Use-Anything applies strict precedence when combining evidence:

1. Local code signals (highest priority)
2. Verified interface evidence (OpenAPI/CLI/SDK context)
3. Context-doc claims (lowest priority, advisory only)

If a context-doc claim conflicts with local code signals, the claim is dropped and recorded in diagnostics.

## Warn + degrade behavior

This feature is non-blocking by default:
- stale docs generate warnings
- conflicting claims are dropped
- oversized context claim payloads are truncated or dropped
- generation continues

Run summary includes:
- `context_docs`
- `context_warnings`
- `context_claims_used`
- `context_claims_dropped`
- `context_conflicts`

## Authoring tips

- Keep this file project-specific; avoid generic SDK reference blocks.
- Separate sections by heading and include a dedicated section like `## How this project uses Supabase`.
- Prefer concrete statements tied to your actual file paths, env names, and runtime boundaries.
- Keep browser/server key rules explicit (for example anon in browser, service role server-only).
- Update `last_verified` whenever code behavior changes.

## Troubleshooting

- `context doc not found; skipping`:
  - pass an absolute path to `--context-doc`.
- stale warnings keep appearing:
  - bump `last_verified` after verifying against current code.
- claims dropped unexpectedly:
  - check for conflict warnings against local code signals and align the doc.
- no context claims used:
  - ensure content is under non-generic sections and within token budget.
