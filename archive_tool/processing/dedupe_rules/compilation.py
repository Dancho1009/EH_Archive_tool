from __future__ import annotations

import re
from collections import defaultdict

from ...models import Record
from .common import is_omnibus_hint, record_index_no, series_anchor_key


def mark_compilation_coverage(
    records: list[Record],
    freeze_existing: bool = False,
    frozen_authors: set[str] | None = None,
) -> None:
    """
    Mark singles as duplicate when covered by an existing compilation range.
    Example: 01/02/03 + 01-03 => singles are considered covered duplicates.
    """
    frozen_authors = frozen_authors or set()
    groups: dict[tuple[str, str], list[Record]] = defaultdict(list)
    for r in records:
        if not r.display_author:
            continue
        if r.display_author in frozen_authors:
            continue
        anchor = series_anchor_key(r)
        if not anchor:
            continue
        groups[(r.display_author, anchor)].append(r)

    gid_seed = 1
    existing_ids = [int(m.group(1)) for r in records for m in [re.match(r"^D(\d+)$", str(r.duplicate_group_id or ""))] if m]
    if existing_ids:
        gid_seed = max(existing_ids) + 1

    hit_groups = 0
    hit_records = 0
    for _, group in groups.items():
        if len(group) < 3:
            continue

        ranges = [
            r
            for r in group
            if r.range_start is not None
            and r.range_end is not None
            and int(r.range_start) <= int(r.range_end)
            and (int(r.range_end) - int(r.range_start)) <= 100
        ]
        omnibus = [r for r in group if is_omnibus_hint(r)]
        if not ranges and not omnibus:
            continue

        singles: list[tuple[Record, int]] = []
        for r in group:
            idx = record_index_no(r)
            if idx is None:
                continue
            singles.append((r, idx))
        if len(singles) < 2:
            continue

        master: Record | None = None
        covered: list[tuple[Record, int]] = []
        reason_fmt = ""

        if ranges:
            ranges.sort(key=lambda x: ((int(x.range_end or 0) - int(x.range_start or 0)), int(x.size_bytes or 0)), reverse=True)
            master = ranges[0]
            start_no, end_no = int(master.range_start or 0), int(master.range_end or 0)
            covered = [(r, idx) for r, idx in singles if start_no <= idx <= end_no and r.record_id != master.record_id]
            reason_fmt = f"被合集覆盖: {start_no}-{end_no} 包含 #{{idx}}"

        if not covered and omnibus:
            omnibus.sort(key=lambda x: int(x.size_bytes or 0), reverse=True)
            master = omnibus[0]
            covered = [(r, idx) for r, idx in singles if r.record_id != master.record_id]
            reason_fmt = "被总集篇覆盖: 包含 #{idx}"

        if master is None or len(covered) < 2:
            continue

        group_id = master.duplicate_group_id or f"D{gid_seed:05d}"
        master.duplicate_group_id = group_id
        master.duplicate_master_id = master.record_id
        gid_seed += 1
        hit_groups += 1

        for item, idx in covered:
            if freeze_existing and str(item.ingest_status or "").lower() != "new":
                continue
            if (
                item.duplicate_status == "严格重复"
                and str(item.duplicate_master_id or "").strip() == master.record_id
                and ("被合集覆盖" in str(item.duplicate_reason or "") or "被总集篇覆盖" in str(item.duplicate_reason or ""))
            ):
                continue
            item.duplicate_status = "严格重复"
            item.duplicate_group_id = group_id
            item.duplicate_master_id = master.record_id
            item.duplicate_with = f"{master.record_id} | {master.raw_name}"
            item.duplicate_source_path = master.full_path
            item.duplicate_reason = reason_fmt.format(idx=idx)
            item.duplicate_confidence = max(item.duplicate_confidence, 92)
            item.manual_review = "是"
            hit_records += 1

    print(f"[CompilationCoverage] groups={hit_groups}, records={hit_records}")
