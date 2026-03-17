"""Typed models used across the probe -> rank -> analyze -> generate -> validate pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class InterfaceCandidate:
    type: str
    location: str
    quality_score: float
    coverage: str
    notes: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "location": self.location,
            "quality_score": self.quality_score,
            "coverage": self.coverage,
            "notes": self.notes,
            "metadata": self.metadata,
        }


@dataclass
class ProbeResult:
    target: str
    target_type: str
    interfaces_found: list[InterfaceCandidate]
    recommended_interface: str | None = None
    reasoning: str | None = None
    source_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "target_type": self.target_type,
            "interfaces_found": [candidate.to_dict() for candidate in self.interfaces_found],
            "recommended_interface": self.recommended_interface,
            "reasoning": self.reasoning,
            "source_metadata": self.source_metadata,
        }


@dataclass
class RankedInterface:
    type: str
    score: float
    reasoning: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "score": self.score,
            "reasoning": self.reasoning,
        }


@dataclass
class RankResult:
    primary: RankedInterface
    secondary: RankedInterface | None
    rejected: list[RankedInterface]

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary": self.primary.to_dict(),
            "secondary": self.secondary.to_dict() if self.secondary else None,
            "rejected": [item.to_dict() for item in self.rejected],
        }


@dataclass
class AnalyzerSetup:
    install: str
    auth: str
    env_vars: list[str]
    prerequisites: list[str]

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> AnalyzerSetup:
        return cls(
            install=str(raw.get("install", "")),
            auth=str(raw.get("auth", "")),
            env_vars=[str(item) for item in raw.get("env_vars", [])],
            prerequisites=[str(item) for item in raw.get("prerequisites", [])],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "install": self.install,
            "auth": self.auth,
            "env_vars": self.env_vars,
            "prerequisites": self.prerequisites,
        }


@dataclass
class Capability:
    name: str
    function: str
    params: dict[str, Any]
    returns: str
    notes: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Capability:
        return cls(
            name=str(raw.get("name", "")),
            function=str(raw.get("function", "")),
            params=dict(raw.get("params", {})),
            returns=str(raw.get("returns", "")),
            notes=str(raw.get("notes", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "function": self.function,
            "params": self.params,
            "returns": self.returns,
            "notes": self.notes,
        }


@dataclass
class CapabilityGroup:
    name: str
    capabilities: list[Capability]

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> CapabilityGroup:
        return cls(
            name=str(raw.get("name", "")),
            capabilities=[Capability.from_dict(item) for item in raw.get("capabilities", [])],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "capabilities": [capability.to_dict() for capability in self.capabilities],
        }


@dataclass
class Workflow:
    name: str
    steps: list[str]
    common_errors: list[str]

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Workflow:
        return cls(
            name=str(raw.get("name", "")),
            steps=[str(item) for item in raw.get("steps", [])],
            common_errors=[str(item) for item in raw.get("common_errors", [])],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "steps": self.steps,
            "common_errors": self.common_errors,
        }


@dataclass
class AnalyzerIR:
    software: str
    interface: str
    version: str
    setup: AnalyzerSetup
    capability_groups: list[CapabilityGroup]
    workflows: list[Workflow]
    gotchas: list[str]
    analysis_sources: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> AnalyzerIR:
        return cls(
            software=str(raw.get("software", "")),
            interface=str(raw.get("interface", "")),
            version=str(raw.get("version", "unknown")),
            setup=AnalyzerSetup.from_dict(dict(raw.get("setup", {}))),
            capability_groups=[CapabilityGroup.from_dict(item) for item in raw.get("capability_groups", [])],
            workflows=[Workflow.from_dict(item) for item in raw.get("workflows", [])],
            gotchas=[str(item) for item in raw.get("gotchas", [])],
            analysis_sources=[str(item) for item in raw.get("analysis_sources", [])],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "software": self.software,
            "interface": self.interface,
            "version": self.version,
            "setup": self.setup.to_dict(),
            "capability_groups": [item.to_dict() for item in self.capability_groups],
            "workflows": [item.to_dict() for item in self.workflows],
            "gotchas": self.gotchas,
            "analysis_sources": self.analysis_sources,
        }


@dataclass
class GeneratedArtifacts:
    skill_path: Path
    reference_paths: dict[str, Path]
    token_counts: dict[str, int]
    line_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_path": str(self.skill_path),
            "reference_paths": {name: str(path) for name, path in self.reference_paths.items()},
            "token_counts": self.token_counts,
            "line_counts": self.line_counts,
        }


@dataclass
class ValidationReport:
    passed: bool
    errors: list[str]
    warnings: list[str]
    metrics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "errors": self.errors,
            "warnings": self.warnings,
            "metrics": self.metrics,
        }


@dataclass
class PipelineResult:
    probe_result: ProbeResult
    rank_result: RankResult
    analysis: AnalyzerIR | None = None
    artifacts: GeneratedArtifacts | None = None
    validation_report: ValidationReport | None = None
    probe_only: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "probe_result": self.probe_result.to_dict(),
            "rank_result": self.rank_result.to_dict(),
            "analysis": self.analysis.to_dict() if self.analysis else None,
            "artifacts": self.artifacts.to_dict() if self.artifacts else None,
            "validation_report": self.validation_report.to_dict() if self.validation_report else None,
            "probe_only": self.probe_only,
        }
