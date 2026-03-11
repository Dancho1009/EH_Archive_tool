from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from urllib import error as urlerror

from ...models import Record
from ...processing.dedupe_rules.common import reason_to_cn
from ..client import deepseek_chat
from .utils import parse_confidence


def _build_candidates(records: list[Record]) -> dict[str, dict]:
    circles: dict[str, dict] = {}
    grouped: dict[str, list[Record]] = defaultdict(list)
    for r in records:
        circle = str(r.circle_std or "").strip()
        if not circle:
            continue
        grouped[circle].append(r)

    for circle, rows in grouped.items():
        author_counter: Counter[str] = Counter()
        examples: list[str] = []
        for r in rows:
            author = str(r.author_std or r.archive_author or "").strip()
            if author:
                author_counter[author] += 1
            if len(examples) < 5:
                examples.append(r.raw_name)
        circles[circle] = {
            "circle": circle,
            "works": len(rows),
            "author_counter": dict(author_counter),
            "examples": examples,
        }
    return circles


def _local_suggest(circle_data: dict) -> tuple[str, int, str] | None:
    author_counter = Counter(circle_data.get("author_counter", {}))
    if not author_counter:
        return None
    top_author, top_count = author_counter.most_common(1)[0]
    total = sum(author_counter.values())
    if total <= 0:
        return None
    ratio = top_count / total
    if top_count >= 2 and ratio >= 0.75:
        conf = int(min(95, 70 + ratio * 25))
        return top_author, conf, f"本地共现推断: {top_author} 占比 {ratio:.0%} ({top_count}/{total})"
    return None


def run_circle_author_suggest(
    records: list[Record],
    args,
    api_key: str,
    output_dir: Path,
) -> dict:
    if not bool(getattr(args, "deepseek_circle_author_suggest", False)):
        return {"enabled": False, "suggested": 0, "ambiguous": 0}

    output_dir.mkdir(parents=True, exist_ok=True)
    circles = _build_candidates(records)
    candidates = [x for x in circles.values() if int(x.get("works", 0)) >= 2]
    configured_limit = int(getattr(args, "deepseek_circle_author_max_circles", -1) or -1)
    batch_size = max(1, int(getattr(args, "deepseek_circle_author_batch_size", 25) or 25))
    min_conf = max(0, min(100, int(getattr(args, "deepseek_circle_author_min_confidence", 70) or 70)))
    candidates = sorted(candidates, key=lambda x: (-int(x.get("works", 0)), x.get("circle", "")))
    detected_total = len(candidates)
    limit = detected_total if configured_limit < 0 else max(0, configured_limit)
    if configured_limit >= 0:
        candidates = candidates[:limit]
    total = len(candidates)
    print(f"[CircleAuthor] candidates={total}, detected={detected_total}, limit={limit}, batch_size={batch_size}, min_conf={min_conf}")
    if total == 0:
        out_path = output_dir / "circle_author_suggestions.json"
        out_path.write_text(json.dumps({"generated_at": int(time.time()), "suggestions": [], "ambiguous": []}, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"enabled": True, "suggested": 0, "ambiguous": 0}

    suggestions: dict[str, dict] = {}
    ambiguous: dict[str, dict] = {}

    # local high-confidence first
    for c in candidates:
        local = _local_suggest(c)
        if local:
            suggestions[c["circle"]] = {
                "circle": c["circle"],
                "author": local[0],
                "confidence": local[1],
                "reason": local[2],
                "source": "local",
            }

    # deepseek for unresolved or low-confidence circles
    pending = [c for c in candidates if c["circle"] not in suggestions]
    batches = [pending[i : i + batch_size] for i in range(0, len(pending), batch_size)]
    start = time.time()
    failed = 0
    for i, batch in enumerate(batches, 1):
        ratio = i / max(1, len(batches))
        bar = "#" * int(30 * ratio) + "-" * (30 - int(30 * ratio))
        print(
            f"\r[CircleAuthor] [{bar}] {i}/{max(1, len(batches))} ({ratio*100:5.1f}%) suggested={len(suggestions)} ambiguous={len(ambiguous)} elapsed={time.time()-start:6.1f}s",
            end="",
            flush=True,
        )
        payload = {
            "circles": [
                {
                    "circle": c["circle"],
                    "works": c["works"],
                    "author_counter": c["author_counter"],
                    "examples": c["examples"],
                }
                for c in batch
            ]
        }
        result = None
        for attempt in range(1, args.deepseek_retries + 2):
            try:
                result = deepseek_chat(
                    api_key,
                    args.deepseek_model,
                    args.deepseek_base_url,
                    (
                        "你是作者-社团关系推断器。基于每个社团的作者共现计数和样本标题，"
                        "返回 JSON: {mapping:[{circle,author,confidence,reason,ambiguous}]}. "
                        "若无法确定作者，ambiguous=true 并给原因。"
                    ),
                    json.dumps(payload, ensure_ascii=False),
                    args.deepseek_timeout,
                )
                break
            except (urlerror.URLError, TimeoutError, KeyError, ValueError, json.JSONDecodeError) as exc:
                if attempt <= args.deepseek_retries:
                    wait = args.deepseek_retry_sleep * (2 ** (attempt - 1))
                    print(f"\n[CircleAuthor][RETRY] batch={i} attempt={attempt} wait={wait:.1f}s error={exc}")
                    time.sleep(wait)
                else:
                    failed += 1
                    print(f"\n[CircleAuthor][FAIL] batch={i} error={exc}")
        if not result:
            continue
        rows = result.get("mapping", [])
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            circle = str(row.get("circle", "")).strip()
            if not circle:
                continue
            author = str(row.get("author", "")).strip()
            conf = parse_confidence(row.get("confidence", 0))
            reason = reason_to_cn(str(row.get("reason", "")).strip())
            is_amb = bool(row.get("ambiguous", False))
            if is_amb or not author or conf < min_conf:
                ambiguous[circle] = {
                    "circle": circle,
                    "author": author,
                    "confidence": conf,
                    "reason": reason or "模型判定歧义或置信度不足",
                    "source": "deepseek",
                }
            else:
                suggestions[circle] = {
                    "circle": circle,
                    "author": author,
                    "confidence": conf,
                    "reason": reason or "DeepSeek推断结果",
                    "source": "deepseek",
                }
    print()
    out_payload = {
        "generated_at": int(time.time()),
        "summary": {
            "candidates": total,
            "suggested": len(suggestions),
            "ambiguous": len(ambiguous),
            "failed_batches": failed,
        },
        "suggestions": sorted(suggestions.values(), key=lambda x: (-int(x["confidence"]), x["circle"])),
        "ambiguous": sorted(ambiguous.values(), key=lambda x: (-int(x["confidence"]), x["circle"])),
    }
    out_path = output_dir / "circle_author_suggestions.json"
    out_path.write_text(json.dumps(out_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[CircleAuthor] suggested={len(suggestions)}, ambiguous={len(ambiguous)}, failed_batches={failed}, file={out_path}")
    return {"enabled": True, "suggested": len(suggestions), "ambiguous": len(ambiguous), "failed_batches": failed}
