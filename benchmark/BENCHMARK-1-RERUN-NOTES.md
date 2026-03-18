# Benchmark 1 Rerun Notes

## Latest Local Validation Run

Date: 2026-03-18 (America/Los_Angeles)

Command used:

```bash
USE_ANYTHING_BENCH_FAKE=1 python3 benchmark/scripts/rerun_benchmark1.py \
  --suite benchmark/comprehensive-codex-suite.json \
  --output-dir benchmark/benchmark-1-run \
  --pilot-targets 2
```

Summary from `benchmark/benchmark-1-run/benchmark_summary.json`:

- `total_runs`: `400`
- `completed_runs`: `400`
- `completion_rate`: `1.0`
- `preflight.passed`: `true`
- `incomplete_reason_counts`: `{}`

## Interpretation

- This run validates rerun orchestration, preflight gate enforcement, archive behavior, and artifact generation.
- Because `USE_ANYTHING_BENCH_FAKE=1` was set, these metrics are harness-validation metrics, not production-quality impact numbers.
- For real Benchmark 1 impact analysis, rerun without fake mode:

```bash
python3 benchmark/scripts/rerun_benchmark1.py \
  --suite benchmark/comprehensive-codex-suite.json \
  --output-dir benchmark/benchmark-1-run \
  --pilot-targets 2
```
