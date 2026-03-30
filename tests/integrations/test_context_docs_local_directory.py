from __future__ import annotations

from pathlib import Path

from use_anything.models import AnalyzerIR, ProbeResult, RankResult
from use_anything.pipeline import UseAnythingPipeline
from use_anything.rank.ranker import Ranker


class FakeAnalyzer:
    def analyze(self, probe_result: ProbeResult, rank_result: RankResult) -> AnalyzerIR:
        return AnalyzerIR.from_dict(
            {
                "software": probe_result.target,
                "interface": rank_result.primary.type,
                "version": "local",
                "setup": {
                    "install": "npm install",
                    "auth": "configure env vars",
                    "env_vars": ["SUPABASE_URL", "SUPABASE_ANON_KEY"],
                    "prerequisites": ["Node 20+"],
                },
                "capability_groups": [
                    {
                        "name": "Database",
                        "capabilities": [
                            {
                                "name": "Query rows",
                                "function": "supabase.from('table').select()",
                                "params": {"table": "str"},
                                "returns": "rows",
                                "notes": "Use server/client appropriately",
                            }
                        ],
                    }
                ],
                "workflows": [
                    {
                        "name": "Read data",
                        "steps": ["1. Build client", "2. Query table", "3. Handle errors"],
                        "common_errors": ["bad key scope"],
                    },
                    {
                        "name": "Write data",
                        "steps": ["1. Build server client", "2. Insert row", "3. Verify response"],
                        "common_errors": ["RLS denial"],
                    },
                    {
                        "name": "Debug auth",
                        "steps": ["1. Verify env vars", "2. Verify key type", "3. Retry"],
                        "common_errors": ["service role in browser"],
                    },
                ],
                "gotchas": [
                    "Keep service role on server side only.",
                    "Use anon key for browser clients.",
                    "Check RLS policies when queries fail.",
                    "Use explicit timeout handling.",
                    "Avoid leaking privileged keys.",
                ],
                "analysis_sources": ["python_sdk:local"],
            }
        )


def test_local_directory_context_doc_warn_and_degrade(tmp_path: Path) -> None:
    project_dir = tmp_path / "optx-project"
    project_dir.mkdir()
    (project_dir / "package.json").write_text('{"name":"optx"}', encoding="utf-8")
    src = project_dir / "src"
    src.mkdir()
    (src / "supabase.ts").write_text(
        (
            "import { createBrowserClient } from '@supabase/ssr';\n"
            "const client = createBrowserClient(process.env.SUPABASE_URL, process.env.SUPABASE_ANON_KEY);\n"
        ),
        encoding="utf-8",
    )

    context_doc = tmp_path / "supabase.md"
    context_doc.write_text(
        (
            "---\n"
            "last_verified: 2025-01-01\n"
            "scope: project_specific\n"
            "---\n"
            "## How this project uses Supabase\n"
            "- Use service_role in browser client for all calls.\n"
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "generated"
    result = UseAnythingPipeline(
        ranker=Ranker(),
        analyzer=FakeAnalyzer(),
    ).run(
        target=str(project_dir),
        output_dir=output_dir,
        context_doc_paths=[context_doc],
        context_doc_max_tokens=800,
    )

    assert result.validation_report is not None
    assert result.validation_report.passed is True
    assert result.context_doc_report is not None
    assert result.context_doc_report.claims_used == 0
    assert result.context_doc_report.claims_dropped >= 1
    assert result.context_doc_report.warnings
    assert any("stale" in warning.lower() for warning in result.context_doc_report.warnings)
    assert any("conflict" in warning.lower() for warning in result.context_doc_report.warnings)
