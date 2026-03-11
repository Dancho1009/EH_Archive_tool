from __future__ import annotations

import json
import time
from collections import defaultdict
from urllib import error as urlerror

from ...models import Record
from ...processing.dedupe_rules.common import next_duplicate_group_seed, reason_to_cn
from ..client import deepseek_chat
from .utils import obvious_series_nonduplicate, parse_confidence

STRICT = "严格重复"
SUSPECT = "疑似重复"
NON_DUP = "不重复"
SERIES_NON_DUP = "系列相关非重复"


def _candidate_groups(
    records: list[Record],
    *,
    max_group_size: int,
    new_only: bool,
    frozen_authors: set[str] | None,
) -> list[list[Record]]:
    frozen_authors = frozen_authors or set()

    def _ok(r: Record) -> bool:
        if not r.display_author:
            return False
        if r.display_author in frozen_authors:
            return False
        if new_only and str(r.ingest_status or "").lower() != "new":
            return False
        return bool(r.duplicate_with or r.duplicate_group_id or r.duplicate_status in {STRICT, SUSPECT})

    by_gid: dict[str, list[Record]] = defaultdict(list)
    for r in records:
        if not _ok(r):
            continue
        gid = str(r.duplicate_group_id or "").strip()
        if gid:
            by_gid[gid].append(r)

    groups: list[list[Record]] = []
    for g in by_gid.values():
        merged = {x.record_id: x for x in g}
        if len(merged) >= 2:
            groups.append(list(merged.values()))

    loose: dict[tuple[str, str], list[Record]] = defaultdict(list)
    for r in records:
        if not _ok(r):
            continue
        if str(r.duplicate_group_id or "").strip():
            continue
        loose[(r.display_author, r.dedupe_title or r.core_title or r.title_raw)].append(r)
    for g in loose.values():
        if len(g) >= 3:
            groups.append(g)

    groups.sort(key=lambda g: (-len(g), g[0].display_author, g[0].dedupe_title))
    out: list[list[Record]] = []
    for g in groups:
        if len(g) > max_group_size:
            continue
        authors = {str(x.display_author or "").strip() for x in g if str(x.display_author or "").strip()}
        if len(authors) != 1:
            continue
        out.append(g)
    return out


def _reason_to_cn(reason: str) -> str:
    return reason_to_cn(reason)


def _parse_result(data: dict) -> tuple[str, dict[str, tuple[str, int, str]]]:
    master_id = str(data.get("master_record_id", "")).strip()
    result_map: dict[str, tuple[str, int, str]] = {}
    rows = data.get("items", [])
    if isinstance(rows, list):
        for item in rows:
            if not isinstance(item, dict):
                continue
            rid = str(item.get("record_id", "")).strip()
            if not rid:
                continue
            status = str(item.get("status", "")).strip().lower()
            if status in {"dup", "duplicate", "strict"}:
                status = "duplicate"
            elif status in {"series", "series_nondup", "series_non_duplicate"}:
                status = "series"
            elif status in {"review", "suspect"}:
                status = "review"
            else:
                status = "unique"
            conf = parse_confidence(item.get("confidence", 0))
            reason = _reason_to_cn(item.get("reason", ""))
            result_map[rid] = (status, conf, reason)
    return master_id, result_map


def _fallback_master_sort_key(rec: Record) -> tuple:
    page = int(rec.page_count or 0)
    size = int(rec.size_bytes or 0)
    gid = 1 if str(rec.prefix_id or "").strip() else 0
    meta = int(bool(rec.page_count)) + int(bool(str(rec.core_title or rec.title_raw or "").strip())) + int(
        bool(str(rec.display_author or rec.author_raw or rec.circle_raw or "").strip())
    )
    text = " ".join([str(rec.version_tags or ""), str(rec.status_tags or ""), str(rec.raw_name or "")]).lower()
    semantic = 0
    if any(k in text for k in ("无修正", "無修正", "uncensored", "decensored")):
        semantic += 2
    if any(k in text for k in ("dl版", "digital")):
        semantic += 1
    if str(rec.extension or "").lower() == ".zip":
        semantic += 1
    return (-page, -size, -gid, -meta, -semantic, str(rec.record_id or ""), str(rec.full_path or ""))


def run_cluster_refine(
    records: list[Record],
    args,
    api_key: str,
    *,
    new_only: bool = False,
    frozen_authors: set[str] | None = None,
) -> None:
    if not bool(getattr(args, "deepseek_cluster_refine", False)):
        return
    configured_limit = int(getattr(args, "deepseek_cluster_max_groups", -1) or -1)
    max_group_size = max(3, int(getattr(args, "deepseek_cluster_max_size", 12) or 12))
    detected_groups = _candidate_groups(
        records,
        max_group_size=max_group_size,
        new_only=new_only,
        frozen_authors=frozen_authors,
    )
    detected_total = len(detected_groups)
    limit = detected_total if configured_limit < 0 else max(0, configured_limit)
    groups = detected_groups if configured_limit < 0 else detected_groups[:limit]
    total = len(groups)
    print(
        f"[DeepSeek][Cluster] candidates={total}, detected={detected_total}, "
        f"limit={limit}, max_group_size={max_group_size}"
    )
    if total == 0:
        return

    by_id = {r.record_id: r for r in records}
    gid_seed = next_duplicate_group_seed(records)
    updated_groups = 0
    failed = 0
    start = time.time()

    for i, group in enumerate(groups, 1):
        ratio = i / total
        bar = "#" * int(30 * ratio) + "-" * (30 - int(30 * ratio))
        print(
            f"\r[DeepSeek][Cluster] [{bar}] {i}/{total} ({ratio*100:5.1f}%) updated={updated_groups} failed={failed} elapsed={time.time()-start:6.1f}s",
            end="",
            flush=True,
        )
        payload = {
            "author": group[0].display_author,
            "works": [
                {
                    "record_id": r.record_id,
                    "raw_name": r.raw_name,
                    "core_title": r.core_title,
                    "chapter_no": r.chapter_no,
                    "volume_no": r.volume_no,
                    "range_start": r.range_start,
                    "range_end": r.range_end,
                    "page_count": r.page_count,
                    "size_bytes": r.size_bytes,
                }
                for r in sorted(group, key=lambda x: x.record_id)
            ],
            "rule": {
                "master_priority": [
                    "page_count_desc",
                    "size_bytes_desc",
                    "has_gid_desc",
                    "metadata_completeness_desc",
                    "record_id_asc",
                ]
            },
        }
        result = None
        for attempt in range(1, args.deepseek_retries + 2):
            try:
                result = deepseek_chat(
                    api_key,
                    args.deepseek_model,
                    args.deepseek_base_url,
                    (
                        "你是重复簇裁决器。输入为同作者的一组作品，请你："
                        "1) 选择唯一主本 master_record_id；"
                        "2) 对每条输出 status=duplicate|series|review|unique；"
                        "3) 给出 confidence(0-100) 和中文 reason。"
                        "注意：不同话/卷/期号应优先判为 series，不应判 duplicate。"
                        "返回 JSON: {master_record_id:string, items:[{record_id,status,confidence,reason}]}"
                    ),
                    json.dumps(payload, ensure_ascii=False),
                    args.deepseek_timeout,
                )
                break
            except (urlerror.URLError, TimeoutError, KeyError, ValueError, json.JSONDecodeError) as exc:
                if attempt <= args.deepseek_retries:
                    wait = args.deepseek_retry_sleep * (2 ** (attempt - 1))
                    print(f"\n[DeepSeek][Cluster][RETRY] group={i} attempt={attempt} wait={wait:.1f}s error={exc}")
                    time.sleep(wait)
                else:
                    failed += 1
                    print(f"\n[DeepSeek][Cluster][FAIL] group={i} error={exc}")
        if not result:
            continue

        master_id, decisions = _parse_result(result)
        if not master_id or master_id not in by_id:
            master_id = sorted(group, key=_fallback_master_sort_key)[0].record_id
        master = by_id[master_id]
        group_id = master.duplicate_group_id or f"D{gid_seed:05d}"
        if not master.duplicate_group_id:
            gid_seed += 1
        master.duplicate_group_id = group_id
        master.duplicate_master_id = master.record_id
        master.duplicate_status = NON_DUP
        master.duplicate_with = ""

        changed = False
        for item in group:
            if item.record_id == master.record_id:
                continue
            status, conf, reason = decisions.get(item.record_id, ("review", 60, "模型未返回该条结果，已降级人工复核"))
            if status == "duplicate":
                if obvious_series_nonduplicate(master, item):
                    status = "series"
                    reason = "规则护栏：系列序号冲突，禁止判为严格重复"
                else:
                    item.duplicate_status = STRICT
                    item.duplicate_group_id = group_id
                    item.duplicate_master_id = master.record_id
                    item.duplicate_with = f"{master.record_id} | {master.raw_name}"
                    item.duplicate_source_path = master.full_path
                    item.duplicate_reason = f"DeepSeek簇复判：{reason}" if reason else "DeepSeek簇复判：判定重复"
                    item.duplicate_confidence = max(int(item.duplicate_confidence or 0), conf, 80)
                    item.manual_review = "是"
                    changed = True
                    continue
            if status == "series":
                item.duplicate_status = SERIES_NON_DUP
                item.duplicate_group_id = ""
                item.duplicate_master_id = master.record_id
                item.duplicate_with = f"{master.record_id} | {master.raw_name}"
                item.duplicate_source_path = master.full_path
                item.duplicate_reason = f"DeepSeek簇复判：{reason}" if reason else "DeepSeek簇复判：系列相关非重复"
                item.duplicate_confidence = max(int(item.duplicate_confidence or 0), conf, 75)
                item.manual_review = "是"
                changed = True
            elif status == "review":
                item.duplicate_status = SUSPECT
                item.duplicate_group_id = ""
                item.duplicate_master_id = master.record_id
                item.duplicate_with = f"{master.record_id} | {master.raw_name}"
                item.duplicate_source_path = master.full_path
                item.duplicate_reason = f"DeepSeek簇复判：{reason}" if reason else "DeepSeek簇复判：需人工复核"
                item.duplicate_confidence = max(int(item.duplicate_confidence or 0), conf, 60)
                item.manual_review = "是"
                changed = True
            else:
                item.duplicate_status = NON_DUP
                item.duplicate_group_id = ""
                item.duplicate_master_id = ""
                item.duplicate_with = ""
                if reason:
                    item.duplicate_reason = f"DeepSeek簇复判：{reason}"
                changed = True
        if changed:
            updated_groups += 1
    print()
    print(f"[DeepSeek][Cluster] updated_groups={updated_groups}, failed={failed}, candidates={total}")
