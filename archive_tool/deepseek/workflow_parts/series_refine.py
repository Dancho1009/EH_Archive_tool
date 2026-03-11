from __future__ import annotations

import json
import time
from collections import defaultdict
from urllib import error as urlerror

from ...models import Record
from ...processing.dedupe_rules.common import reason_to_cn
from ..client import deepseek_chat
from .utils import normalize_missing_numbers, parse_confidence, sequence_hint, series_present_numbers


def run_series_missing_refine(
    records: list[Record],
    args,
    api_key: str,
    new_only: bool = False,
    frozen_authors: set[str] | None = None,
) -> None:
    """Use DeepSeek to detect likely missing installments in series groups."""
    frozen_authors = frozen_authors or set()
    grouped: dict[tuple[str, str], list[Record]] = defaultdict(list)
    for r in records:
        key = str(r.series_key or r.dedupe_title or "").strip()
        if not r.display_author or not key:
            continue
        if r.work_type == "magazine":
            continue
        if r.display_author in frozen_authors:
            continue
        grouped[(r.display_author, key)].append(r)

    candidates: list[tuple[tuple[str, str], list[Record]]] = []
    for key, group in grouped.items():
        if len(group) < 2:
            continue
        if new_only and not any(str(x.ingest_status or "").lower() == "new" for x in group):
            continue
        if all(r.series_missing == "是" for r in group):
            continue
        if not any(sequence_hint(r) for r in group):
            continue
        candidates.append((key, group))

    detected_total = len(candidates)
    configured_limit = int(getattr(args, "deepseek_series_max_groups", -1) or -1)
    limit = detected_total if configured_limit < 0 else max(0, configured_limit)
    candidates = candidates[:limit]
    total = len(candidates)
    print(f"[SeriesMissing][DeepSeek] candidates={total}, detected={detected_total}, limit={limit}, model={args.deepseek_model}")
    if total == 0:
        return

    updated_groups = 0
    failed = 0
    start = time.time()
    min_conf = int(getattr(args, "deepseek_series_min_confidence", 70))

    for i, ((author, dedupe_title), group) in enumerate(candidates, 1):
        ratio = i / total
        bar = "#" * int(30 * ratio) + "-" * (30 - int(30 * ratio))
        print(
            f"\r[SeriesMissing][DeepSeek] [{bar}] {i}/{total} ({ratio*100:5.1f}%) updated={updated_groups} failed={failed} elapsed={time.time()-start:6.1f}s",
            end="",
            flush=True,
        )

        payload = {
            "author": author,
            "series_key": dedupe_title,
            "works": [
                {
                    "record_id": r.record_id,
                    "raw_name": r.raw_name,
                    "chapter_no": r.chapter_no,
                    "volume_no": r.volume_no,
                    "range_start": r.range_start,
                    "range_end": r.range_end,
                }
                for r in sorted(group, key=lambda x: (x.volume_no, x.chapter_no, x.raw_name))
            ],
        }

        result = None
        for attempt in range(1, args.deepseek_retries + 2):
            try:
                result = deepseek_chat(
                    api_key,
                    args.deepseek_model,
                    args.deepseek_base_url,
                    (
                        "你是系列完整性审查器。给定同作者同标题下的一组作品，判断是否存在缺失期数。"
                        "请保持保守，只有在序号信息明确时才判定缺失。"
                        "返回JSON: {has_missing:boolean,index_type:chapter|volume|unknown,missing_numbers:number[],confidence:0-100,reason:string}"
                    ),
                    json.dumps(payload, ensure_ascii=False),
                    args.deepseek_timeout,
                )
                break
            except (urlerror.URLError, TimeoutError, KeyError, ValueError, json.JSONDecodeError) as exc:
                if attempt <= args.deepseek_retries:
                    wait = args.deepseek_retry_sleep * (2 ** (attempt - 1))
                    print(f"\n[SeriesMissing][DeepSeek][RETRY] group={i} attempt={attempt} wait={wait:.1f}s error={exc}")
                    time.sleep(wait)
                else:
                    failed += 1
                    print(f"\n[SeriesMissing][DeepSeek][FAIL] group={i} error={exc}")
        if not result:
            continue

        has_missing = bool(result.get("has_missing", False))
        confidence = parse_confidence(result.get("confidence", 0))
        index_type = str(result.get("index_type", "unknown") or "unknown").strip().lower()
        if index_type not in {"chapter", "volume"}:
            index_type = "chapter"
        missing_numbers = normalize_missing_numbers(result.get("missing_numbers", []))
        reason = reason_to_cn(str(result.get("reason", "")).strip())
        if not has_missing or confidence < min_conf or not missing_numbers:
            continue

        present_numbers = series_present_numbers(group, index_type)
        present_text = ",".join(str(x) for x in present_numbers)
        missing_text = ",".join(str(x) for x in missing_numbers)
        if not reason:
            reason = f"模型判断缺失: {missing_text}"
        reason = f"DeepSeek系列缺失复核：{reason}"

        series_key = f"{author}|{dedupe_title}"
        for r in group:
            if new_only and str(r.ingest_status or "").lower() != "new":
                continue
            r.series_key = series_key
            r.series_index_type = index_type
            if present_text:
                r.series_indices = present_text
            r.series_missing = "是"
            r.series_missing_numbers = missing_text
            r.series_missing_reason = reason
            r.series_missing_confidence = max(r.series_missing_confidence, confidence)
            r.manual_review = "是"
            if reason not in (r.notes or ""):
                r.notes = f"{r.notes} | {reason}".strip(" |")
        updated_groups += 1

    print()
    print(f"[SeriesMissing][DeepSeek] updated_groups={updated_groups}, failed={failed}, candidates={total}")


