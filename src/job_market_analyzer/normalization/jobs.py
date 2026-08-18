"""Shared contracts for source-specific job normalization."""


class NormalizationError(ValueError):
    """Malformed data for one source item that a batch may safely skip."""
