from __future__ import annotations

import pytest
from jsonschema import ValidationError, validate

from use_anything.analyze.schema import ANALYZER_IR_SCHEMA
from use_anything.models import AnalyzerIR


def _base_payload() -> dict:
    return {
        "software": "requests",
        "interface": "python_sdk",
        "version": "2.32.3",
        "setup": {
            "install": "pip install requests",
            "auth": "none",
            "env_vars": [],
            "prerequisites": [],
        },
        "capability_groups": [],
        "workflows": [],
        "gotchas": ["set timeout"],
        "analysis_sources": ["python_sdk:pypi:requests"],
    }


def test_analyzer_schema_accepts_payload_without_gotcha_provenance() -> None:
    payload = _base_payload()

    validate(payload, ANALYZER_IR_SCHEMA)


def test_analyzer_schema_rejects_incomplete_gotcha_provenance_entry() -> None:
    payload = _base_payload()
    payload["gotcha_provenance"] = [
        {
            "gotcha": "set timeout",
            "source": "docs:https://example.com",
            "evidence": "request can hang",
            # missing required url
        }
    ]

    with pytest.raises(ValidationError, match="url"):
        validate(payload, ANALYZER_IR_SCHEMA)


def test_analyzer_ir_backwards_compat_defaults_gotcha_provenance_to_empty_list() -> None:
    ir = AnalyzerIR.from_dict(_base_payload())

    assert ir.gotcha_provenance == []


def test_analyzer_ir_parses_optional_gotcha_provenance_entries() -> None:
    payload = _base_payload()
    payload["gotcha_provenance"] = [
        {
            "gotcha": "set timeout",
            "source": "github_issue:https://github.com/psf/requests/issues/1234",
            "evidence": "timeouts required on unstable networks",
            "url": "https://github.com/psf/requests/issues/1234",
        }
    ]

    ir = AnalyzerIR.from_dict(payload)

    assert len(ir.gotcha_provenance) == 1
    assert ir.gotcha_provenance[0].source.startswith("github_issue")
