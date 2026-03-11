from __future__ import annotations

from collections import defaultdict

from ...models import Record
from .common import gid_master_score, next_duplicate_group_seed, normalized_gid


def mark_gid_duplicates(
    records: list[Record],
    freeze_existing: bool = False,
    frozen_authors: set[str] | None = None,
) -> None:
    """
    Highest-priority dedupe rule:
    same gid (prefix_id) => strict duplicate.
    """
    frozen_authors = frozen_authors or set()
    grouped: dict[str, list[Record]] = defaultdict(list)
    for r in records:
        gid = normalized_gid(r)
        if not gid:
            continue
        if r.display_author in frozen_authors:
            continue
        grouped[gid].append(r)

    gid_seed = next_duplicate_group_seed(records)
    hit_groups = 0
    hit_records = 0

    for gid, group in grouped.items():
        if len(group) < 2:
            continue

        if freeze_existing:
            existing = [x for x in group if str(x.ingest_status or "").lower() != "new"]
            if existing:
                master = sorted(existing, key=gid_master_score, reverse=True)[0]
            else:
                master = sorted(group, key=gid_master_score, reverse=True)[0]
        else:
            master = sorted(group, key=gid_master_score, reverse=True)[0]

        group_id = master.duplicate_group_id or f"D{gid_seed:05d}"
        if not master.duplicate_group_id:
            gid_seed += 1
        if not (freeze_existing and str(master.ingest_status or "").lower() != "new"):
            master.duplicate_group_id = group_id
            master.duplicate_master_id = master.record_id

        changed_any = False
        for item in group:
            if item.record_id == master.record_id:
                continue
            if freeze_existing and str(item.ingest_status or "").lower() != "new":
                continue
            item.duplicate_status = "严格重复"
            item.duplicate_group_id = group_id
            item.duplicate_master_id = master.record_id
            item.duplicate_with = f"{master.record_id} | {master.raw_name}"
            item.duplicate_source_path = master.full_path
            item.duplicate_reason = f"GID相同: {gid}"
            item.duplicate_confidence = max(item.duplicate_confidence, 99)
            item.manual_review = "是"
            changed_any = True
            hit_records += 1
        if changed_any:
            hit_groups += 1

    print(f"[GID] groups={hit_groups}, records={hit_records}")
