"""Deterministic interface ranking."""

from __future__ import annotations

from use_anything.models import ProbeResult, RankedInterface, RankResult

CRITERIA_WEIGHTS = {
    "structured_io": 0.25,
    "error_quality": 0.15,
    "statefulness": 0.15,
    "auth_complexity": 0.10,
    "documentation_depth": 0.20,
    "ecosystem_adoption": 0.15,
}

BASE_INTERFACE_SCORES = {
    "openapi_spec": {
        "structured_io": 1.0,
        "error_quality": 0.9,
        "statefulness": 0.9,
        "auth_complexity": 0.7,
        "documentation_depth": 0.9,
        "ecosystem_adoption": 0.8,
    },
    "rest_api_docs": {
        "structured_io": 0.8,
        "error_quality": 0.7,
        "statefulness": 0.9,
        "auth_complexity": 0.6,
        "documentation_depth": 0.7,
        "ecosystem_adoption": 0.8,
    },
    "python_sdk": {
        "structured_io": 0.95,
        "error_quality": 0.9,
        "statefulness": 0.9,
        "auth_complexity": 0.85,
        "documentation_depth": 0.8,
        "ecosystem_adoption": 0.9,
    },
    "node_sdk": {
        "structured_io": 0.9,
        "error_quality": 0.85,
        "statefulness": 0.85,
        "auth_complexity": 0.75,
        "documentation_depth": 0.8,
        "ecosystem_adoption": 0.85,
    },
    "cli_tool": {
        "structured_io": 0.45,
        "error_quality": 0.55,
        "statefulness": 0.7,
        "auth_complexity": 0.85,
        "documentation_depth": 0.6,
        "ecosystem_adoption": 0.75,
    },
    "existing_skill": {
        "structured_io": 0.75,
        "error_quality": 0.75,
        "statefulness": 0.9,
        "auth_complexity": 0.9,
        "documentation_depth": 0.6,
        "ecosystem_adoption": 0.7,
    },
    "llms_txt": {
        "structured_io": 0.7,
        "error_quality": 0.65,
        "statefulness": 0.9,
        "auth_complexity": 0.9,
        "documentation_depth": 0.85,
        "ecosystem_adoption": 0.75,
    },
}

INTERFACE_PRIORITY_ORDER = [
    "openapi_spec",
    "python_sdk",
    "node_sdk",
    "graphql_api",
    "grpc_api",
    "rest_api_docs",
    "existing_skill",
    "llms_txt",
    "cli_tool",
]


class Ranker:
    """Score and rank discovered interfaces for agent usability."""

    def rank(self, probe_result: ProbeResult) -> RankResult:
        scored = []
        for candidate in probe_result.interfaces_found:
            base = BASE_INTERFACE_SCORES.get(candidate.type, BASE_INTERFACE_SCORES["cli_tool"])
            score = sum(base[key] * weight for key, weight in CRITERIA_WEIGHTS.items())
            adjusted = (score * 0.7) + (candidate.quality_score * 0.3)
            scored.append(
                RankedInterface(
                    type=candidate.type,
                    score=round(adjusted, 4),
                    reasoning=self._reason_for(candidate.type),
                )
            )

        scored.sort(
            key=lambda item: (
                item.score,
                self._priority_for(item.type),
            ),
            reverse=True,
        )
        if not scored:
            raise ValueError("Cannot rank interfaces: no candidates available")

        primary = scored[0]
        secondary = scored[1] if len(scored) > 1 else None
        rejected = scored[2:] if len(scored) > 2 else []
        return RankResult(primary=primary, secondary=secondary, rejected=rejected)

    def _reason_for(self, interface_type: str) -> str:
        reasons = {
            "python_sdk": "Typed importable API with strong ecosystem support.",
            "openapi_spec": "Fully structured machine-readable API contract.",
            "rest_api_docs": "REST interface is usable but less structured than SDKs.",
            "cli_tool": "CLI interface available as fallback when SDK is unavailable.",
            "existing_skill": "Existing skill content can be used as acceleration input.",
            "llms_txt": "LLM-optimized docs can accelerate synthesis and workflow extraction.",
        }
        return reasons.get(interface_type, "Scored by weighted usability heuristics.")

    def _priority_for(self, interface_type: str) -> int:
        try:
            return len(INTERFACE_PRIORITY_ORDER) - INTERFACE_PRIORITY_ORDER.index(interface_type)
        except ValueError:
            return 0
