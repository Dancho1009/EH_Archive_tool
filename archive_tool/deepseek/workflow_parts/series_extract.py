from __future__ import annotations

import json
import re
import time
from urllib import error as urlerror

from ...models import Record
from ...processing.parsing_text import normalize_key, normalize_series_key, normalize_text
from ...processing.dedupe_rules.common import reason_to_cn
from ..client import deepseek_chat
from .utils import parse_confidence

SERIES_HINT_RE = re.compile(
    r"(?:第\s*\d{1,4}\s*(?:話|话|巻|卷)|[#＃]\s*\d{1,4}|vol\.?\s*\d+(?:\.\d+)?|no\.?\s*\d{1,4}|[A-Za-z\u3040-\u30ff\u3400-\u9fff]\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
RANGE_RE = re.compile(r"^\s*(\d{1,4})\s*[-~～]\s*(\d{1,4})\s*$")
NUM_RE = re.compile(r"^\d+(?:\.\d+)?$")


def _has_index(rec: Record) -> bool:
    return bool(str(rec.chapter_no or "").strip() or str(rec.volume_no or "").strip() or rec.range_start is not None or rec.range_end is not None)


def _candidate(rec: Record, *, new_only: bool, frozen_authors: set[str] | None) -> bool:
    frozen_authors = frozen_authors or set()
    if not rec.display_author:
        return False
    if rec.display_author in frozen_authors:
        return False
    if new_only and str(rec.ingest_status or "").lower() != "new":
        return False
    if rec.work_type == "magazine":
        return False
    text = str(rec.title_raw or rec.raw_name or "").strip()
    if not text:
        return False
    if not SERIES_HINT_RE.search(text):
        return False
    if not _has_index(rec):
        return True
    core = str(rec.core_title or "").strip()
    core_has_num = bool(re.search(r"\d+(?:\.\d+)?", core))
    return core_has_num


def _parse_result(data: dict) -> tuple[str, str, str, int, str]:
    series_title = normalize_text(str(data.get("series_title", "")).strip())
    index_type = str(data.get("index_type", "")).strip().lower()
    if index_type not in {"chapter", "volume", "range", "none"}:
        index_type = "none"
    index_no = str(data.get("index_no", "")).strip()
    confidence = parse_confidence(data.get("confidence", 0))
    reason = reason_to_cn(str(data.get("reason", "")).strip())
    return series_title, index_type, index_no, confidence, reason if reason else ""


def _apply(rec: Record, series_title: str, index_type: str, index_no: str) -> bool:
    changed = False
    if series_title:
        title_norm = normalize_text(series_title)
        if title_norm and title_norm != rec.core_title:
            rec.core_title = title_norm
            rec.dedupe_title = normalize_key(rec.core_title)
            rec.series_key = normalize_series_key(rec.core_title) or rec.dedupe_title
            changed = True

    idx = str(index_no or "").strip()
    if index_type == "range":
        m = RANGE_RE.match(idx)
        if m:
            start_no, end_no = int(m.group(1)), int(m.group(2))
            if start_no <= end_no:
                if rec.range_start != start_no or rec.range_end != end_no:
                    rec.range_start, rec.range_end = start_no, end_no
                    rec.chapter_no = ""
                    rec.volume_no = ""
                    changed = True
    elif index_type == "chapter":
        if NUM_RE.match(idx):
            if rec.chapter_no != idx:
                rec.chapter_no = idx
                rec.volume_no = ""
                changed = True
    elif index_type == "volume":
        if NUM_RE.match(idx):
            if rec.volume_no != idx:
                rec.volume_no = idx
                changed = True
    return changed


def run_series_extract_refine(
    records: list[Record],
    args,
    api_key: str,
    *,
    new_only: bool = False,
    frozen_authors: set[str] | None = None,
) -> None:
    if not bool(getattr(args, "deepseek_series_extract", False)):
        return

    configured_limit = int(getattr(args, "deepseek_series_extract_max_candidates", -1) or -1)
    min_conf = max(0, min(100, int(getattr(args, "deepseek_series_extract_min_confidence", 70) or 70)))
    candidates = [r for r in records if _candidate(r, new_only=new_only, frozen_authors=frozen_authors)]
    detected_total = len(candidates)
    limit = detected_total if configured_limit < 0 else max(0, configured_limit)
    if configured_limit >= 0:
        candidates = candidates[:limit]
    total = len(candidates)
    print(f"[DeepSeek][SeriesExtract] candidates={total}, detected={detected_total}, limit={limit}, min_conf={min_conf}")
    if total == 0:
        return

    updated = 0
    failed = 0
    start = time.time()
    for i, rec in enumerate(candidates, 1):
        ratio = i / total
        bar = "#" * int(30 * ratio) + "-" * (30 - int(30 * ratio))
        print(
            f"\r[DeepSeek][SeriesExtract] [{bar}] {i}/{total} ({ratio*100:5.1f}%) updated={updated} failed={failed} elapsed={time.time()-start:6.1f}s",
            end="",
            flush=True,
        )
        payload = {
            "raw_name": rec.raw_name,
            "title_raw": rec.title_raw,
            "current_core_title": rec.core_title,
            "current_chapter_no": rec.chapter_no,
            "current_volume_no": rec.volume_no,
            "current_range_start": rec.range_start,
            "current_range_end": rec.range_end,
        }
        result = None
        for attempt in range(1, args.deepseek_retries + 2):
            try:
                result = deepseek_chat(
                    api_key,
                    args.deepseek_model,
                    args.deepseek_base_url,
                    (
                        "你是作品系列信息提取器。"
                        "目标是从标题中提取“系列标题”和“系列序号”。"
                        "序号类型 index_type 只能是 chapter|volume|range|none。"
                        "index_no: chapter/volume 用数字或小数(如2.5)，range 用 1-15。"
                        "不要臆测，不确定时返回 index_type=none。"
                        "返回 JSON: {series_title,index_type,index_no,confidence,reason}。"
                    ),
                    json.dumps(payload, ensure_ascii=False),
                    args.deepseek_timeout,
                )
                break
            except (urlerror.URLError, TimeoutError, KeyError, ValueError, json.JSONDecodeError) as exc:
                if attempt <= args.deepseek_retries:
                    wait = args.deepseek_retry_sleep * (2 ** (attempt - 1))
                    print(f"\n[DeepSeek][SeriesExtract][RETRY] record={rec.record_id} attempt={attempt} wait={wait:.1f}s error={exc}")
                    time.sleep(wait)
                else:
                    failed += 1
                    print(f"\n[DeepSeek][SeriesExtract][FAIL] record={rec.record_id} error={exc}")
        if not result:
            continue

        series_title, index_type, index_no, confidence, reason = _parse_result(result)
        if confidence < min_conf:
            continue
        if _apply(rec, series_title, index_type, index_no):
            note = f"DeepSeek系列提取: {reason}" if reason else "DeepSeek系列提取"
            rec.notes = f"{rec.notes} | {note}".strip(" |")
            updated += 1
    print()
    print(f"[DeepSeek][SeriesExtract] updated={updated}, failed={failed}, candidates={total}")
