from __future__ import annotations

import json
import ssl
import time
from pathlib import Path
from urllib import error as urlerror

from ...models import Record
from ...policy import is_blacklisted_name
from ..author_cache import load_author_merge_cache, save_author_merge_cache
from ..client import deepseek_chat, parse_confidence


def run_author_merge(
    records: list[Record],
    args,
    api_key: str,
    policy: dict | None = None,
    only_new: bool = False,
    frozen_authors: set[str] | None = None,
    cache_file: Path | None = None,
) -> dict:
    """Canonicalize author/circle aliases via DeepSeek."""
    policy = policy or {}
    frozen_authors = frozen_authors or set()

    def _eligible(r: Record) -> bool:
        if not (r.author_std or r.circle_std):
            return False
        if only_new and str(r.ingest_status or "").lower() != "new":
            return False
        if r.display_author and r.display_author in frozen_authors:
            return False
        key = r.author_std or r.circle_std
        if is_blacklisted_name(key, policy):
            return False
        return True

    all_unique_names = sorted({(r.author_std or r.circle_std) for r in records if _eligible(r)})
    total_unique_names = len(all_unique_names)
    configured_limit = int(getattr(args, "deepseek_author_merge_max_names", -1) or -1)
    if configured_limit < 0:
        names = all_unique_names
        limit = total_unique_names
    else:
        limit = max(0, configured_limit)
        names = all_unique_names[:limit]
    if not names:
        print("[AuthorMerge] candidates=0")
        return {
            "input_unique_names": total_unique_names,
            "submitted_names": 0,
            "cache_hit": 0,
            "mapped": 0,
            "updated_records": 0,
        }

    cache_mapping = load_author_merge_cache(cache_file) if cache_file else {}
    mapping: dict[str, tuple[str, int]] = {}
    pending_names: list[str] = []
    cache_hit = 0
    min_conf = int(args.deepseek_author_merge_min_confidence)
    for n in names:
        hit = cache_mapping.get(n)
        if hit and hit[0] and hit[1] >= min_conf:
            mapping[n] = hit
            cache_hit += 1
        else:
            pending_names.append(n)

    batches = [pending_names[i : i + args.deepseek_author_merge_batch_size] for i in range(0, len(pending_names), args.deepseek_author_merge_batch_size)]
    print(
        f"[AuthorMerge] candidates={len(names)}, cache_hit={cache_hit}, pending={len(pending_names)}, "
        f"limit={limit}, batches={len(batches)}, model={args.deepseek_model}"
    )
    start = time.time()
    consecutive_fail_batches = 0
    stop_after = max(1, int(getattr(args, "deepseek_author_merge_stop_after_fail_batches", 2)))
    cache_dirty = False

    for i, batch in enumerate(batches, 1):
        ratio = i / max(1, len(batches))
        bar = "#" * int(30 * ratio) + "-" * (30 - int(30 * ratio))
        print(
            f"\r[AuthorMerge] [{bar}] {i}/{max(1,len(batches))} ({ratio*100:5.1f}%) "
            f"mapped={len(mapping)} elapsed={time.time()-start:6.1f}s",
            end="",
            flush=True,
        )
        result = None
        for attempt in range(1, args.deepseek_retries + 2):
            try:
                result = deepseek_chat(
                    api_key,
                    args.deepseek_model,
                    args.deepseek_base_url,
                    "Normalize author aliases. Return JSON mapping list with raw/canonical/confidence.",
                    json.dumps({"names": batch}, ensure_ascii=False),
                    args.deepseek_timeout,
                )
                break
            except (urlerror.URLError, TimeoutError, KeyError, ValueError, json.JSONDecodeError, ssl.SSLError, ConnectionResetError, OSError) as exc:
                if attempt <= args.deepseek_retries:
                    wait = args.deepseek_retry_sleep * (2 ** (attempt - 1))
                    print(f"\n[AuthorMerge][RETRY] batch={i} attempt={attempt} wait={wait:.1f}s error={exc}")
                    time.sleep(wait)
                else:
                    print(f"\n[AuthorMerge][FAIL] batch={i} error={exc}")
        if not result:
            consecutive_fail_batches += 1
            if consecutive_fail_batches >= stop_after:
                print(f"\n[AuthorMerge][STOP] 连续失败批次={consecutive_fail_batches}，提前终止")
                break
            continue

        consecutive_fail_batches = 0
        rows = result.get("mapping", [])
        if isinstance(rows, list):
            for item in rows:
                if not isinstance(item, dict):
                    continue
                raw = str(item.get("raw", "")).strip()
                can = str(item.get("canonical", "")).strip()
                conf = parse_confidence(item.get("confidence", 0))
                if raw and can:
                    mapping[raw] = (can, conf)
                    cache_mapping[raw] = (can, conf)
                    cache_dirty = True
    print()
    if cache_file and cache_dirty:
        save_author_merge_cache(cache_file, cache_mapping, model=str(args.deepseek_model))
        print(f"[AuthorMerge][Cache] saved: {cache_file}")

    updated = 0
    for r in records:
        if only_new and str(r.ingest_status or "").lower() != "new":
            continue
        if r.display_author and r.display_author in frozen_authors:
            continue
        key = r.author_std or r.circle_std
        if not key:
            continue
        if is_blacklisted_name(key, policy):
            continue
        mapped = mapping.get(key)
        if mapped and mapped[1] >= args.deepseek_author_merge_min_confidence and mapped[0]:
            if r.archive_author != mapped[0]:
                r.archive_author = mapped[0]
                if r.work_type != "magazine":
                    r.display_author = mapped[0]
                updated += 1
    print(f"[AuthorMerge] mapped={len(mapping)}, updated_records={updated}")
    return {
        "input_unique_names": total_unique_names,
        "submitted_names": len(pending_names),
        "cache_hit": cache_hit,
        "mapped": len(mapping),
        "updated_records": updated,
    }


