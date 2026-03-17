"""Token counting helpers with a safe fallback when model encodings are unknown."""

from __future__ import annotations

import re

import tiktoken

DEFAULT_ENCODING = "cl100k_base"


def count_tokens(text: str, model: str | None = None) -> int:
    """Count tokens for a text payload.

    Falls back to the default encoding and then to a rough word-based estimate if needed.
    """

    if not text:
        return 0

    encoding = None
    if model:
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            encoding = None

    if encoding is None:
        try:
            encoding = tiktoken.get_encoding(DEFAULT_ENCODING)
        except Exception:
            encoding = None

    if encoding is not None:
        return len(encoding.encode(text))

    # Fallback estimate for environments where tiktoken fails unexpectedly.
    return max(1, int(len(re.findall(r"\S+", text)) * 1.3))
