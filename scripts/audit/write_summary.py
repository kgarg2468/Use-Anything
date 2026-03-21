#!/usr/bin/env python3
"""Write audit summary JSON contract and optionally enforce blocking policy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from use_anything.audit.reporting import build_audit_summary, should_block_merge


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate", required=True, help="Gate identifier (e.g., coverage-gate)")
    parser.add_argument("--status", required=True, choices=["passed", "failed"], help="Gate status")
    parser.add_argument("--duration-seconds", type=float, default=0.0, help="Wall time duration for the gate")
    parser.add_argument("--failure-category", default="", help="Failure category when status=failed")
    parser.add_argument(
        "--module-coverage-json",
        type=Path,
        help="Optional JSON file containing module_coverage object or coverage_gate result payload",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/audit/summary.json"),
        help="Output summary path",
    )
    parser.add_argument(
        "--enforce-risk-blocking",
        action="store_true",
        help="Exit 1 when the summary is merge-blocking by risk policy",
    )
    return parser.parse_args()


def _load_module_coverage(path: Path | None) -> dict[str, float]:
    if path is None or not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("module_coverage"), dict):
        module_coverage = payload["module_coverage"]
    elif isinstance(payload, dict):
        module_coverage = payload
    else:
        module_coverage = {}

    output: dict[str, float] = {}
    for key, value in module_coverage.items():
        if isinstance(key, str) and isinstance(value, int | float):
            output[key] = round(float(value), 2)
    return output


def main() -> int:
    args = parse_args()
    summary = build_audit_summary(
        gate=args.gate,
        status=args.status,
        duration_seconds=args.duration_seconds,
        failure_category=args.failure_category or None,
        module_coverage=_load_module_coverage(args.module_coverage_json),
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary.to_dict(), indent=2, sort_keys=True))

    if args.enforce_risk_blocking and should_block_merge(summary):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
