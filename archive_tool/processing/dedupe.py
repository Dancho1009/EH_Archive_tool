from __future__ import annotations

"""
Backward-compatible dedupe facade.

Public API remains unchanged for callers.
Implementations live in `archive_tool.processing.dedupe_rules`.
"""

from .dedupe_rules import (
    dedupe_records,
    finalize_sort_keys,
    mark_compilation_coverage,
    mark_gid_duplicates,
    mark_series_missing,
    mark_suggested_authors,
    normalize_author_alias_by_gid,
    normalize_duplicate_reason_language,
    normalize_strict_duplicates,
)

__all__ = [
    "dedupe_records",
    "finalize_sort_keys",
    "mark_compilation_coverage",
    "mark_gid_duplicates",
    "mark_series_missing",
    "mark_suggested_authors",
    "normalize_author_alias_by_gid",
    "normalize_duplicate_reason_language",
    "normalize_strict_duplicates",
]
