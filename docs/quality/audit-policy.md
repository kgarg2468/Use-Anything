# Use-Anything Audit Policy

## Purpose
This policy defines how quality gates are evaluated and when merges are blocked for audit-related failures.

## Summary Contract
Every CI quality gate must emit `artifacts/audit/summary.json` with this shape:

- `gate`: gate identifier (for example `coverage-gate`)
- `status`: `passed` or `failed`
- `duration_seconds`: floating-point wall duration
- `failure_category`: one of `timeout`, `network`, `auth`, `rate_limit`, `schema`, `command_failed`, `permission`, `regression`, or `null` on pass
- `risk_level`: `low`, `medium`, `high`, `critical`
- `module_coverage`: module-to-percentage map when coverage data is available

## Risk-Based Merge Blocking
Merge blocking is enforced by failure severity:

- Block merges for failed gates with `risk_level` `high` or `critical`.
- Do not block automatically for `medium` failures; surface as warnings and track with follow-up issues.
- Always treat `regression` as `critical`.

## CI Expectations
- PR required gates: `lint`, `test-fast`, `coverage-gate`, `test-live-smoke`.
- Nightly gates: deep deterministic tests, benchmark regression tests, live smoke checks, and coverage gate.
- Coverage gate target: overall `>=92%`, module floor `>=85%`, and `__main__` floor `>=70%`.
