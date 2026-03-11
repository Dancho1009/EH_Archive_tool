from __future__ import annotations

import re
from collections import defaultdict
from difflib import SequenceMatcher

from ...models import Record
from .common import next_duplicate_group_seed, normalized_gid, record_index_no, series_mismatch_reason

STRICT = "严格重复"
SUSPECT = "疑似重复"
NON_DUP = "不重复"
SERIES_NON_DUP = "系列相关非重复"


def _completeness_score(rec: Record) -> int:
    score = 0
    if int(rec.page_count or 0) > 0:
        score += 1
    if str(rec.core_title or rec.title_raw or "").strip():
        score += 1
    if str(rec.display_author or rec.author_raw or rec.circle_raw or rec.circle_std or "").strip():
        score += 1
    return score


def _semantic_quality_score(rec: Record) -> int:
    text = " ".join(
        [
            str(rec.version_tags or ""),
            str(rec.status_tags or ""),
            str(rec.raw_name or ""),
            str(rec.source_info or ""),
        ]
    ).lower()
    score = 0
    if any(k in text for k in ("无修正", "無修正", "uncensored", "decensored")):
        score += 2
    if any(k in text for k in ("dl版", "digital")):
        score += 1
    if any(k in text for k in ("完全版", "完整版", "total", "omnibus")):
        score += 1
    if str(rec.extension or "").lower() == ".zip":
        score += 1
    if str(rec.group_tag or "").strip():
        score += 1
    return score


def _master_sort_key(rec: Record) -> tuple:
    page = int(rec.page_count or 0)
    size = int(rec.size_bytes or 0)
    gid = 1 if str(rec.prefix_id or "").strip() else 0
    meta = _completeness_score(rec)
    semantic = _semantic_quality_score(rec)
    record_id = str(rec.record_id or "")
    full_path = str(rec.full_path or "")
    return (-page, -size, -gid, -meta, -semantic, record_id, full_path)


def _extract_master_id(rec: Record) -> str:
    if rec.duplicate_master_id:
        return str(rec.duplicate_master_id).strip()
    if rec.duplicate_with:
        return str(rec.duplicate_with).split("|", 1)[0].strip()
    return ""


def _title_key(rec: Record) -> str:
    s = str(rec.dedupe_title or rec.core_title or rec.title_raw or "").lower().strip()
    s = re.sub(r"[^0-9a-z\u3040-\u30ff\u3400-\u9fff]+", "", s)
    return s


def _title_similarity(a: Record, b: Record) -> float:
    ka, kb = _title_key(a), _title_key(b)
    if not ka or not kb:
        return 0.0
    return SequenceMatcher(None, ka, kb).ratio()


def _bad_strict_link(a: Record, b: Record) -> tuple[bool, str]:
    gid_a = normalized_gid(a)
    gid_b = normalized_gid(b)
    # Same gid is the highest-priority strict signal, do not downgrade by author mismatch.
    if gid_a and gid_b and gid_a == gid_b:
        return False, ""

    a_author = str(a.display_author or "").strip()
    b_author = str(b.display_author or "").strip()
    if a_author and b_author and a_author != b_author:
        return True, "跨作者重复关系，自动降级人工复核"

    # If reason says same gid but linked master gid is different, force downgrade.
    reason = str(a.duplicate_reason or "")
    if "被合集覆盖" in reason or "被总集篇覆盖" in reason:
        return False, ""
    if "GID相同" in reason:
        if gid_a and gid_b and gid_a != gid_b:
            return True, "GID冲突：重复来源与当前记录GID不一致"

    sim = _title_similarity(a, b)
    # Different gid + very low title similarity should not be strict duplicate.
    if sim < 0.35:
        return True, "标题语义差异过大，自动降级人工复核"
    return False, ""


def normalize_strict_duplicates(
    records: list[Record],
    freeze_existing: bool = False,
    frozen_authors: set[str] | None = None,
) -> None:
    """
    Ensure strict-duplicate clusters have exactly one master.

    Master selection priority:
    1) page_count higher
    2) size_bytes larger
    3) has gid
    4) metadata completeness (page/title/author or circle)
    5) semantic quality
    6) stable tie-breaker (record_id/full_path)
    """
    frozen_authors = frozen_authors or set()
    by_id = {r.record_id: r for r in records}

    def _editable(rec: Record) -> bool:
        if frozen_authors and rec.display_author in frozen_authors:
            return False
        if freeze_existing and str(rec.ingest_status or "").lower() != "new":
            return False
        return True

    # 1) downgrade obviously bad strict links first
    downgraded = 0
    for r in records:
        if r.duplicate_status != STRICT:
            continue
        mid = _extract_master_id(r)
        if not mid or mid == r.record_id:
            continue
        m = by_id.get(mid)
        if not m:
            continue
        bad, why = _bad_strict_link(r, m)
        if bad and _editable(r):
            r.duplicate_status = SUSPECT
            r.duplicate_group_id = ""
            r.duplicate_master_id = ""
            r.duplicate_reason = why
            r.manual_review = "是"
            downgraded += 1
    if downgraded:
        print(f"[StrictMaster] downgraded_bad_links={downgraded}")

    # 2) build DSU over strict rows
    strict_rows = [r for r in records if r.duplicate_status == STRICT and _editable(r)]
    if len(strict_rows) < 2:
        return

    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(a: str, b: str) -> None:
        if not a or not b or a == b:
            return
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for r in strict_rows:
        master_id = _extract_master_id(r)
        if master_id and master_id in by_id:
            union(r.record_id, master_id)

    # union by duplicate_group_id for strict rows
    group_by_gid: dict[str, list[Record]] = defaultdict(list)
    for r in strict_rows:
        gid = str(r.duplicate_group_id or "").strip()
        if gid:
            group_by_gid[gid].append(r)
    for g in group_by_gid.values():
        root = g[0].record_id
        for r in g[1:]:
            union(root, r.record_id)

    strict_clusters: dict[str, list[Record]] = defaultdict(list)
    for r in strict_rows:
        strict_clusters[find(r.record_id)].append(r)

    # index all records by duplicate_group_id so non-strict anchor masters can join candidate set
    all_by_gid: dict[str, list[Record]] = defaultdict(list)
    for r in records:
        gid = str(r.duplicate_group_id or "").strip()
        if gid:
            all_by_gid[gid].append(r)

    gid_seed = next_duplicate_group_seed(records)
    normalized = 0
    for cluster in strict_clusters.values():
        if len(cluster) < 2:
            continue

        candidate_map: dict[str, Record] = {r.record_id: r for r in cluster}

        # add explicit masters referenced by strict rows
        for r in cluster:
            mid = _extract_master_id(r)
            if mid and mid in by_id:
                m = by_id[mid]
                if not frozen_authors or m.display_author not in frozen_authors:
                    candidate_map[m.record_id] = m

        # add all rows in same duplicate_group_id (including non-strict anchors)
        for r in cluster:
            gid = str(r.duplicate_group_id or "").strip()
            if not gid:
                continue
            for x in all_by_gid.get(gid, []):
                if not frozen_authors or x.display_author not in frozen_authors:
                    candidate_map[x.record_id] = x

        candidates = list(candidate_map.values())
        if len(candidates) < 2:
            continue

        candidates.sort(key=_master_sort_key)
        master = candidates[0]

        group_id = str(master.duplicate_group_id or "").strip()
        if not group_id:
            for x in candidates:
                gid = str(x.duplicate_group_id or "").strip()
                if gid:
                    group_id = gid
                    break
        if not group_id:
            group_id = f"D{gid_seed:05d}"
            gid_seed += 1

        if _editable(master):
            master.duplicate_group_id = group_id
            master.duplicate_master_id = master.record_id
            master.duplicate_status = NON_DUP
            master.duplicate_with = ""

        for item in cluster:
            if item.record_id == master.record_id:
                continue
            covered_hint = "被合集覆盖" in str(item.duplicate_reason or "") or "被总集篇覆盖" in str(item.duplicate_reason or "")
            idx = record_index_no(item)
            covered_by_master_range = (
                master.range_start is not None
                and master.range_end is not None
                and idx is not None
                and int(master.range_start) <= int(idx) <= int(master.range_end)
            )
            mismatch = series_mismatch_reason(master, item)
            if mismatch and not covered_hint and not covered_by_master_range:
                item.duplicate_status = SERIES_NON_DUP
                item.duplicate_group_id = ""
                item.duplicate_master_id = master.record_id
                item.duplicate_with = f"{master.record_id} | {master.raw_name}"
                item.duplicate_source_path = master.full_path
                item.duplicate_reason = mismatch
                item.manual_review = "是"
                normalized += 1
                continue

            item.duplicate_status = STRICT
            item.duplicate_group_id = group_id
            item.duplicate_master_id = master.record_id
            item.duplicate_with = f"{master.record_id} | {master.raw_name}"
            item.duplicate_source_path = master.full_path
            if not item.duplicate_reason:
                item.duplicate_reason = "严格重复（主本归一）"
            item.manual_review = "是"
            normalized += 1

    if normalized:
        print(f"[StrictMaster] normalized={normalized}")
