from __future__ import annotations

from use_anything.generate.skill_merge import merge_skill_markdown


def test_merge_skill_replaces_canonical_sections_and_preserves_custom() -> None:
    existing = """---
name: requests
description: existing
license: MIT
metadata:
  owner: team
---

# requests

## Setup

old setup

## Custom notes

keep this section

## Important constraints

old constraints
"""
    generated = """---
name: requests
description: generated
license: MIT
metadata:
  generated_by: use-anything
---

# requests

## Setup

new setup

## Key concepts

new concepts

## Important constraints

new constraints

## Quick reference

new quick ref
"""

    merged = merge_skill_markdown(existing_skill=existing, generated_skill=generated)

    assert "new setup" in merged
    assert "new constraints" in merged
    assert "old setup" not in merged
    assert "old constraints" not in merged
    assert "## Custom notes" in merged
    assert "keep this section" in merged
