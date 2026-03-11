from __future__ import annotations

import json
import time
from urllib import error as urlerror

from ...models import Record
from ...processing.dedupe_rules.common import reason_to_cn
from ..client import deepseek_chat
from .utils import obvious_series_nonduplicate, parse_confidence


def collect_candidates(
    records: list[Record],
    mode: str,
    limit: int,
    new_only: bool = False,
    frozen_authors: set[str] | None = None,
) -> list[Record]:
    frozen_authors = frozen_authors or set()

    def _ok(r: Record) -> bool:
        if frozen_authors and r.display_author in frozen_authors:
            return False
        if new_only and str(r.ingest_status or "").lower() != "new":
            return False
        return True

    if mode == "strict":
        pool = [r for r in records if _ok(r) and r.duplicate_status == "疑似重复" and r.duplicate_with]
    elif mode == "balanced":
        pool = [r for r in records if _ok(r) and r.duplicate_status == "疑似重复" and r.duplicate_with]
    else:
        pool = [r for r in records if _ok(r) and r.duplicate_with and r.duplicate_status != "系列相关非重复"]
    if int(limit) < 0:
        return pool
    return pool[: int(limit)]


def run_dedupe_refine(
    records: list[Record],
    args,
    api_key: str,
    new_only: bool = False,
    frozen_authors: set[str] | None = None,
) -> None:
    by_id = {r.record_id: r for r in records}
    candidates = collect_candidates(
        records,
        args.deepseek_candidate_mode,
        args.deepseek_max_candidates,
        new_only=new_only,
        frozen_authors=frozen_authors,
    )
    total = len(candidates)
    configured_limit = int(getattr(args, "deepseek_max_candidates", -1) or -1)
    limit = total if configured_limit < 0 else max(0, configured_limit)
    print(f"[DeepSeek] candidates={total}, limit={limit}, mode={args.deepseek_candidate_mode}, model={args.deepseek_model}")
    if total == 0:
        return

    start = time.time()
    refined = 0
    failed = 0
    for i, r in enumerate(candidates, 1):
        ratio = i / total
        bar = "#" * int(30 * ratio) + "-" * (30 - int(30 * ratio))
        print(f"\r[DeepSeek] [{bar}] {i}/{total} ({ratio*100:5.1f}%) in-flight refined={refined} failed={failed} elapsed={time.time()-start:6.1f}s", end="", flush=True)
        mid = r.duplicate_with.split("|", 1)[0].strip() if r.duplicate_with else ""
        m = by_id.get(mid)
        if not m:
            continue
        result = None
        for attempt in range(1, args.deepseek_retries + 2):
            try:
                result = deepseek_chat(
                    api_key,
                    args.deepseek_model,
                    args.deepseek_base_url,
                    "Judge duplicate. Return JSON {decision,confidence,reason}.",
                    json.dumps(
                        {
                            "record_a": {"name": m.raw_name, "author": m.display_author, "title": m.core_title, "volume": m.volume_no, "chapter": m.chapter_no},
                            "record_b": {"name": r.raw_name, "author": r.display_author, "title": r.core_title, "volume": r.volume_no, "chapter": r.chapter_no},
                        },
                        ensure_ascii=False,
                    ),
                    args.deepseek_timeout,
                )
                break
            except (urlerror.URLError, TimeoutError, KeyError, ValueError, json.JSONDecodeError) as exc:
                if attempt <= args.deepseek_retries:
                    wait = args.deepseek_retry_sleep * (2 ** (attempt - 1))
                    print(f"\n[DeepSeek][RETRY] record={r.record_id} attempt={attempt} wait={wait:.1f}s error={exc}")
                    time.sleep(wait)
                else:
                    failed += 1
                    print(f"\n[DeepSeek][FAIL] record={r.record_id} error={exc}")
        if not result:
            continue

        decision = str(result.get("decision", "")).lower().strip()
        confidence = parse_confidence(result.get("confidence", 0))
        reason = reason_to_cn(str(result.get("reason", "")).strip())
        if decision == "duplicate":
            if obvious_series_nonduplicate(m, r):
                r.duplicate_status = "系列相关非重复"
                r.duplicate_reason = "规则护栏：卷/话/期号不同，禁止改判为严格重复"
                r.manual_review = "是"
                refined += 1
                continue
            r.duplicate_status = "严格重复"
            r.duplicate_reason = f"DeepSeek语义复判：{reason}" if reason else "DeepSeek语义复判：判定重复"
            r.duplicate_confidence = max(80, confidence)
            refined += 1
        elif decision == "not_duplicate":
            r.duplicate_status = "系列相关非重复"
            r.duplicate_reason = f"DeepSeek语义复判：{reason}" if reason else "DeepSeek语义复判：判定非重复"
            r.duplicate_confidence = max(80, confidence)
            r.manual_review = "是"
            refined += 1
        elif decision == "review":
            r.duplicate_status = "疑似重复"
            r.duplicate_reason = f"DeepSeek语义复判：{reason}" if reason else r.duplicate_reason
            r.manual_review = "是"
            refined += 1
    print()
    print(f"[DeepSeek] refined={refined}, failed={failed}, candidates={total}")
