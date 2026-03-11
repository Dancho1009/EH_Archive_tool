from .dedupe import (
    dedupe_records,
    finalize_sort_keys,
    mark_compilation_coverage,
    mark_gid_duplicates,
    mark_series_missing,
    mark_suggested_authors,
)
from .anomaly import detect_anomalies
from .parsing import (
    fill_missing_sizes,
    iter_all_paths,
    parse_record,
    parse_with_progress,
    signature,
)

__all__ = [
    "parse_record",
    "parse_with_progress",
    "iter_all_paths",
    "fill_missing_sizes",
    "signature",
    "mark_gid_duplicates",
    "mark_suggested_authors",
    "dedupe_records",
    "mark_compilation_coverage",
    "mark_series_missing",
    "finalize_sort_keys",
    "detect_anomalies",
]
