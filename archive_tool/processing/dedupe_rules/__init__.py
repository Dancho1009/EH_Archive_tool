from .author_alias import normalize_author_alias_by_gid
from .author_suggest import mark_suggested_authors
from .common import normalize_duplicate_reason_language
from .compilation import mark_compilation_coverage
from .gid import mark_gid_duplicates
from .series_missing import mark_series_missing
from .sorting import finalize_sort_keys
from .strict_master import normalize_strict_duplicates
from .title_rules import dedupe_records

__all__ = [
    "dedupe_records",
    "finalize_sort_keys",
    "mark_compilation_coverage",
    "mark_gid_duplicates",
    "mark_series_missing",
    "mark_suggested_authors",
    "normalize_strict_duplicates",
    "normalize_author_alias_by_gid",
    "normalize_duplicate_reason_language",
]
