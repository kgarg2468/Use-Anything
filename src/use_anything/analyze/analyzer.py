"""Analyzer orchestrator."""

from __future__ import annotations

from jsonschema import ValidationError, validate

from use_anything.analyze.interface_handlers import build_interface_context
from use_anything.analyze.llm_client import LLMClient
from use_anything.analyze.prompts import SYSTEM_PROMPT, build_analysis_prompt
from use_anything.analyze.schema import ANALYZER_IR_SCHEMA
from use_anything.exceptions import AnalyzeError
from use_anything.models import AnalyzerIR, ProbeResult, RankResult


class Analyzer:
    """Deep-read the selected interface and return structured IR."""

    def __init__(
        self,
        *,
        llm_client: LLMClient | None = None,
        model: str | None = None,
        timeout_seconds: int | None = None,
        max_retries: int | None = None,
    ) -> None:
        if llm_client is not None:
            self.llm_client = llm_client
            return
        self.llm_client = LLMClient(
            model=model,
            timeout_seconds=timeout_seconds or 60,
            max_retries=2 if max_retries is None else max_retries,
        )

    def analyze(self, probe_result: ProbeResult, rank_result: RankResult) -> AnalyzerIR:
        interface_context = build_interface_context(
            probe_result=probe_result,
            interface_type=rank_result.primary.type,
        )
        user_prompt = build_analysis_prompt(
            probe_result=probe_result,
            rank_result=rank_result,
            interface_context=interface_context.summary,
            analysis_sources=interface_context.sources,
            context_claims=[
                str(item.get("text", "")).strip()
                for item in probe_result.source_metadata.get("context_doc_claims", [])
                if isinstance(item, dict) and str(item.get("text", "")).strip()
            ],
        )
        payload = self.llm_client.analyze(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            schema=ANALYZER_IR_SCHEMA,
        )
        if not payload.get("analysis_sources"):
            payload["analysis_sources"] = interface_context.sources or []

        try:
            validate(payload, ANALYZER_IR_SCHEMA)
        except ValidationError as exc:
            raise AnalyzeError(f"Analyzer payload did not match schema: {exc.message}") from exc

        return AnalyzerIR.from_dict(payload)
