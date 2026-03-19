# Benchmark 1 Live Rerun Progress

- Start (UTC): 2026-03-19T04:10:35Z
- Start (Local): 2026-03-18 21:10:35 PDT
- Mode: live (non-fake)
- Runner: `python3 benchmark/scripts/rerun_benchmark1.py`
- Suite: `benchmark/comprehensive-codex-suite.json`
- Output: `benchmark/benchmark-1-run`
- Pilot targets: `2`
- Expected runs: `400`

## Command

```bash
unset USE_ANYTHING_BENCH_FAKE
python3 benchmark/scripts/rerun_benchmark1.py \
  --suite benchmark/comprehensive-codex-suite.json \
  --output-dir benchmark/benchmark-1-run \
  --pilot-targets 2
```

## Acceptance

- `total_runs == 400`
- `completion_rate >= 0.95`
- `incomplete_reason_counts.missing_execution_config == 0`
- Live integrity: sampled artifacts show non-template responses and non-zero durations

## Checkpoints

- 2026-03-19T04:10:35Z kickoff created
- 2026-03-19T04:16:41Z detached orchestrator started (live mode)
