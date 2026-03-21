from __future__ import annotations

import runpy


def test_module_entrypoint_invokes_cli_main(monkeypatch) -> None:
    calls = {"count": 0}

    def fake_main() -> None:
        calls["count"] += 1

    monkeypatch.setattr("use_anything.cli.main", fake_main)
    runpy.run_module("use_anything", run_name="__main__")

    assert calls["count"] == 1
