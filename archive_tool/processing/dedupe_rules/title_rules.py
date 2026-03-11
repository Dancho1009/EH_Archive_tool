from __future__ import annotations

from collections import defaultdict

from ...models import Record
from .common import series_mismatch_reason


def dedupe_records(
    records: list[Record],
    freeze_existing: bool = False,
    frozen_authors: set[str] | None = None,
) -> None:
    """Rule-based dedupe labels within same author + dedupe_title."""
    frozen_authors = frozen_authors or set()
    grouped: dict[tuple[str, str], list[Record]] = defaultdict(list)

    def _title_bucket(r: Record) -> str:
        has_series_idx = bool(str(r.chapter_no or "").strip() or str(r.volume_no or "").strip() or r.range_start is not None or r.range_end is not None)
        if has_series_idx and str(r.series_key or "").strip():
            return str(r.series_key).strip()
        return str(r.dedupe_title or "").strip()

    for r in records:
        bucket = _title_bucket(r)
        if not r.display_author or not bucket:
            continue
        if r.display_author in frozen_authors:
            continue
        grouped[(r.display_author, bucket)].append(r)
    gid = 1
    for group in grouped.values():
        if len(group) < 2:
            continue
        group.sort(key=lambda x: (x.volume_no, x.chapter_no, x.raw_name))
        master = group[0]
        for item in group[1:]:
            if freeze_existing and str(item.ingest_status or "").lower() != "new":
                continue
            mismatch_reason = series_mismatch_reason(master, item)
            if mismatch_reason:
                item.duplicate_status = "系列相关非重复"
                item.duplicate_reason = mismatch_reason
                item.duplicate_with = f"{master.record_id} | {master.raw_name}"
                item.duplicate_source_path = master.full_path
                item.manual_review = "是"
                continue
            if not master.duplicate_group_id:
                master.duplicate_group_id = f"D{gid:05d}"
            if not (freeze_existing and str(master.ingest_status or "").lower() != "new"):
                master.duplicate_master_id = master.record_id
            item.duplicate_status = "严格重复"
            item.duplicate_group_id = master.duplicate_group_id
            item.duplicate_master_id = master.record_id
            item.duplicate_with = f"{master.record_id} | {master.raw_name}"
            item.duplicate_source_path = master.full_path
            item.duplicate_reason = "核心标题一致"
            item.duplicate_confidence = 95
        gid += 1
