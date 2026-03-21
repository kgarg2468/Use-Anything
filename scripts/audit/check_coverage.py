#!/usr/bin/env python3
"""Enforce coverage floors and changed-module coverage presence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from use_anything.audit.coverage_gate import (
    build_module_coverage,
    changed_modules_from_paths,
    evaluate_coverage_thresholds,
    overall_percent_from_payload,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage-json", type=Path, required=True, help="Path to coverage json output")
    parser.add_argument("--changed-files", type=Path, help="Optional newline-delimited changed file list")
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=Path("artifacts/audit/coverage_gate.json"),
        help="Output path for coverage gate summary JSON",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = json.loads(args.coverage_json.read_text(encoding="utf-8"))
    module_coverage = build_module_coverage(payload)
    overall = overall_percent_from_payload(payload)

    changed_modules: list[str] = []
    if args.changed_files and args.changed_files.exists():
        changed_paths = [
            line.strip()
            for line in args.changed_files.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        changed_modules = changed_modules_from_paths(changed_paths)

    result = evaluate_coverage_thresholds(
        overall_percent=overall,
        module_coverage=module_coverage,
        changed_modules=changed_modules,
    )

    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
