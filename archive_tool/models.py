from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Record:
    """One parsed work entry."""

    record_id: str
    raw_name: str
    full_path: str
    parent_path: str
    is_dir: bool
    extension: str
    ingest_status: str = "new"
    prefix_id: str = ""
    author_raw: str = ""
    circle_raw: str = ""
    author_std: str = ""
    circle_std: str = ""
    archive_author: str = ""
    display_author: str = ""
    title_raw: str = ""
    core_title: str = ""
    dedupe_title: str = ""
    chapter_no: str = ""
    range_start: int | None = None
    range_end: int | None = None
    volume_no: str = ""
    source_info: str = ""
    ip_info: str = ""
    size_bytes: int = 0
    size_text: str = ""
    page_count: int = 0
    page_count_text: str = ""
    language_tags: str = ""
    version_tags: str = ""
    group_tag: str = ""
    status_tags: str = ""
    work_type: str = "unknown"
    author_affinity_status: str = "无"
    suggested_author: str = ""
    suggested_author_reason: str = ""
    suggested_author_confidence: int = 0
    duplicate_status: str = "不重复"
    duplicate_group_id: str = ""
    duplicate_master_id: str = ""
    duplicate_with: str = ""
    duplicate_source_path: str = ""
    duplicate_reason: str = ""
    duplicate_confidence: int = 0
    series_key: str = ""
    series_index_type: str = ""
    series_indices: str = ""
    series_missing: str = "否"
    series_missing_numbers: str = ""
    series_missing_reason: str = ""
    series_missing_confidence: int = 0
    manual_review: str = "否"
    author_sort_key: str = ""
    title_sort_key: str = ""
    risk_level: str = ""
    risk_flags: str = ""
    risk_detail: str = ""
    notes: str = ""
