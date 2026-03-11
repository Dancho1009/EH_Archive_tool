from __future__ import annotations

"""Backward-compatible parsing facade."""

from .parsing_record import fill_missing_sizes, parse_record
from .parsing_scan import iter_all_paths, parse_with_progress, signature
from .parsing_text import normalize_text

__all__ = [
    "parse_record",
    "parse_with_progress",
    "iter_all_paths",
    "fill_missing_sizes",
    "signature",
    "normalize_text",
]
