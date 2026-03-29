# Phase 3 Quality Gates (14/15)

This document defines completion criteria for the remaining quality gates in Phase 3.

## Gate 14: Gotcha Extraction Quality

Done criteria:

- Evidence mining includes both:
  - GitHub issues
  - Stack Overflow questions
- Cross-source evidence is deduplicated and ranked.
- Failures in either external source degrade gracefully to warnings (pipeline continues).
- Analyzer context surfaces merged external provenance entries.

Deterministic tests:

```bash
uv run pytest -q tests/test_analyze_evidence.py tests/test_analyze_handlers.py
```

## Gate 15: Functional Validation

Done criteria:

- Runtime functional validation stays optional and non-breaking.
- Pipeline wiring executes functional checks only when enabled.
- Failures are captured as structured step reports (not uncaught crashes).

Deterministic tests:

```bash
uv run pytest -q tests/test_functional_validation.py tests/test_pipeline.py -k "functional"
```

## Combined Phase 3 Deterministic Check

```bash
uv run pytest -m "not live_smoke" -q
```
