"""JSON schema for analyzer outputs."""

from __future__ import annotations

ANALYZER_IR_SCHEMA: dict = {
    "type": "object",
    "required": [
        "software",
        "interface",
        "version",
        "setup",
        "capability_groups",
        "workflows",
        "gotchas",
    ],
    "properties": {
        "software": {"type": "string", "minLength": 1},
        "interface": {"type": "string", "minLength": 1},
        "version": {"type": "string", "minLength": 1},
        "setup": {
            "type": "object",
            "required": ["install", "auth", "env_vars", "prerequisites"],
            "properties": {
                "install": {"type": "string"},
                "auth": {"type": "string"},
                "env_vars": {"type": "array", "items": {"type": "string"}},
                "prerequisites": {"type": "array", "items": {"type": "string"}},
            },
        },
        "capability_groups": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "capabilities"],
                "properties": {
                    "name": {"type": "string"},
                    "capabilities": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["name", "function", "params", "returns", "notes"],
                            "properties": {
                                "name": {"type": "string"},
                                "function": {"type": "string"},
                                "params": {"type": "object"},
                                "returns": {"type": "string"},
                                "notes": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
        "workflows": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "steps", "common_errors"],
                "properties": {
                    "name": {"type": "string"},
                    "steps": {"type": "array", "items": {"type": "string"}},
                    "common_errors": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "gotchas": {"type": "array", "items": {"type": "string"}},
    },
}
