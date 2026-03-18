"""Benchmark runner orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from use_anything.benchmark.models import BenchmarkSuite


class BenchmarkRunner:
    """Run benchmark suites and return structured summaries."""

    def run(
        self,
        *,
        suite: BenchmarkSuite,
        output_dir: Path,
        configs: list[str],
        agent: str,
    ) -> dict[str, Any]:
        return {
            "benchmark_summary": {
                "suite": suite.name,
                "agent": agent,
                "configs": configs,
                "total_runs": 0,
            },
            "output_dir": str(output_dir),
        }
