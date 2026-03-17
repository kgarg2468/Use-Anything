"""Analyzer orchestrator."""

from __future__ import annotations

from jsonschema import ValidationError, validate

from use_anything.analyze.llm_client import LLMClient
from use_anything.analyze.prompts import SYSTEM_PROMPT, build_analysis_prompt
from use_anything.analyze.schema import ANALYZER_IR_SCHEMA
from use_anything.exceptions import AnalyzeError
from use_anything.models import AnalyzerIR, ProbeResult, RankResult


class Analyzer:
    """Deep-read the selected interface and return structured IR."""

    def __init__(self, *, llm_client: LLMClient | None = None, model: str | None = None) -> None:
        self.llm_client = llm_client or LLMClient(model=model)

    def analyze(self, probe_result: ProbeResult, rank_result: RankResult) -> AnalyzerIR:
        user_prompt = build_analysis_prompt(probe_result=probe_result, rank_result=rank_result)
        payload = self.llm_client.analyze(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            schema=ANALYZER_IR_SCHEMA,
        )

        try:
            validate(payload, ANALYZER_IR_SCHEMA)
        except ValidationError as exc:
            raise AnalyzeError(f"Analyzer payload did not match schema: {exc.message}") from exc

        return AnalyzerIR.from_dict(payload)
