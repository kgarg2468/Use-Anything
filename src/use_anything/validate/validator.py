"""Validator for spec and quality checks."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from use_anything.models import ValidationReport
from use_anything.utils.tokens import count_tokens


class Validator:
    """Validate generated skill directories against MVP quality and format gates."""

    def validate_directory(self, skill_dir: Path | str) -> ValidationReport:
        root = Path(skill_dir)
        errors: list[str] = []
        warnings: list[str] = []
        metrics: dict[str, int] = {}

        skill_path = root / "SKILL.md"
        if not skill_path.exists():
            return ValidationReport(
                passed=False,
                errors=["SKILL.md is missing from the provided directory"],
                warnings=[],
                metrics={},
            )

        content = skill_path.read_text()
        frontmatter, body = self._split_frontmatter(content)
        if frontmatter is None:
            errors.append("SKILL.md frontmatter is missing or invalid")
            return ValidationReport(passed=False, errors=errors, warnings=warnings, metrics=metrics)

        meta = self._parse_frontmatter(frontmatter, errors)
        self._validate_frontmatter_fields(meta, errors)

        metrics["skill_lines"] = len(body.splitlines())
        metrics["skill_tokens"] = count_tokens(body)

        if metrics["skill_lines"] > 500:
            errors.append(f"SKILL.md body has {metrics['skill_lines']} lines (limit 500)")
        if metrics["skill_tokens"] > 5000:
            errors.append(f"SKILL.md body has {metrics['skill_tokens']} tokens (limit 5000)")

        self._validate_sections(body, errors)

        if re.search(r"\b(TODO|TBD|insert here)\b", content, flags=re.IGNORECASE):
            errors.append("SKILL.md contains placeholder text (TODO/TBD/insert here)")

        references = root / "references"
        if not references.exists():
            warnings.append("references/ directory is missing")

        return ValidationReport(
            passed=not errors,
            errors=errors,
            warnings=warnings,
            metrics=metrics,
        )

    def _split_frontmatter(self, content: str) -> tuple[str | None, str]:
        match = re.match(r"^---\n(.*?)\n---\n(.*)$", content, flags=re.DOTALL)
        if not match:
            return None, content
        return match.group(1), match.group(2)

    def _parse_frontmatter(self, frontmatter: str, errors: list[str]) -> dict:
        try:
            parsed = yaml.safe_load(frontmatter) or {}
        except yaml.YAMLError as exc:
            errors.append(f"Frontmatter YAML parse error: {exc}")
            return {}

        if not isinstance(parsed, dict):
            errors.append("Frontmatter must be a YAML object")
            return {}
        return parsed

    def _validate_frontmatter_fields(self, meta: dict, errors: list[str]) -> None:
        name = str(meta.get("name", ""))
        description = str(meta.get("description", ""))

        if not name:
            errors.append("Frontmatter 'name' is required")
        elif not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
            errors.append("Frontmatter 'name' must be lowercase with hyphens only")
        elif len(name) > 64:
            errors.append("Frontmatter 'name' must be <= 64 characters")

        if not description:
            errors.append("Frontmatter 'description' is required")
        elif len(description) > 1024:
            errors.append("Frontmatter 'description' must be <= 1024 characters")

        trigger_keywords = ["use", "asked", "workflow", "api", "task"]
        matches = sum(1 for keyword in trigger_keywords if keyword in description.lower())
        if matches < 3:
            errors.append("Frontmatter 'description' should include at least 3 trigger phrases")

    def _validate_sections(self, body: str, errors: list[str]) -> None:
        required_sections = [
            "## Setup",
            "## Core workflows",
            "## Important constraints",
            "## Quick reference",
            "## When to use references",
        ]

        for section in required_sections:
            if section not in body:
                errors.append(f"Missing required section: {section}")

        workflows_section = self._extract_section(body, "## Core workflows")
        workflow_count = len(re.findall(r"^### ", workflows_section, flags=re.MULTILINE))
        if workflow_count < 3:
            errors.append("Core workflows section must include at least 3 workflows")

        constraints_section = self._extract_section(body, "## Important constraints")
        gotcha_count = len(re.findall(r"^- ", constraints_section, flags=re.MULTILINE))
        if gotcha_count < 5:
            errors.append("Important constraints section must include at least 5 bullets")

        quick_reference_section = self._extract_section(body, "## Quick reference")
        table_rows = [
            line
            for line in quick_reference_section.splitlines()
            if line.strip().startswith("|") and "---" not in line
        ]
        data_rows = max(0, len(table_rows) - 1)
        if data_rows < 10:
            errors.append("Quick reference must include at least 10 operations")

    def _extract_section(self, body: str, header: str) -> str:
        pattern = re.escape(header) + r"\n(.*?)(?:\n## |\Z)"
        match = re.search(pattern, body, flags=re.DOTALL)
        if not match:
            return ""
        return match.group(1)
