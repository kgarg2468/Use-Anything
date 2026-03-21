from __future__ import annotations

from use_anything.generate.skill_writer import (
    _ensure_gotcha_count,
    _ensure_workflow_count,
    render_skill_markdown,
)
from use_anything.models import AnalyzerIR, Capability, CapabilityGroup, Workflow


def _minimal_ir() -> AnalyzerIR:
    return AnalyzerIR.from_dict(
        {
            "software": "demo",
            "interface": "python_sdk",
            "version": "1.0.0",
            "setup": {
                "install": "pip install demo",
                "auth": "none",
                "env_vars": [],
                "prerequisites": [],
            },
            "capability_groups": [],
            "workflows": [],
            "gotchas": [],
            "analysis_sources": ["python_sdk:pypi:demo"],
        }
    )


def test_ensure_workflow_count_uses_capabilities_before_default_workflows() -> None:
    workflows = [
        Workflow(name="Existing", steps=["1. run existing"], common_errors=[]),
    ]
    groups = [
        CapabilityGroup(
            name="Core",
            capabilities=[
                Capability(name="Fetch", function="demo.fetch()", params={}, returns="dict", notes=""),
                Capability(name="Update", function="demo.update()", params={}, returns="dict", notes=""),
            ],
        )
    ]

    out = _ensure_workflow_count(workflows, groups)

    assert len(out) == 3
    assert out[0].name == "Existing"
    assert out[1].name.startswith("Use Fetch")
    assert out[2].name.startswith("Use Update")


def test_ensure_workflow_count_falls_back_to_default_workflows() -> None:
    out = _ensure_workflow_count([], [])

    assert len(out) == 3
    assert all(item.name.startswith("Default workflow") for item in out)


def test_ensure_gotcha_count_backfills_defaults() -> None:
    gotchas = _ensure_gotcha_count(["custom gotcha"])

    assert len(gotchas) == 5
    assert "custom gotcha" in gotchas


def test_render_skill_markdown_uses_default_workflows_and_gotchas() -> None:
    markdown = render_skill_markdown(_minimal_ir(), source_interface="python_sdk")

    assert markdown.count("### ") >= 3
    constraints_section = markdown.split("## Important constraints", 1)[1]
    assert constraints_section.count("- ") >= 5
