"""Custom exception types for Use-Anything."""

from __future__ import annotations


class UseAnythingError(Exception):
    """Base exception for all Use-Anything failures."""


class UnsupportedTargetError(UseAnythingError):
    """Raised when the input target type is not supported."""


class ProbeError(UseAnythingError):
    """Raised when probing fails."""


class AnalyzeError(UseAnythingError):
    """Raised when analysis fails."""


class GenerationError(UseAnythingError):
    """Raised when skill generation fails."""


class ValidationFailure(UseAnythingError):
    """Raised when validator cannot run correctly."""
