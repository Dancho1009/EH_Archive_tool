from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from ..models import Record


def feedback_path(output_dir: Path) -> Path:
    return output_dir / "审核反馈.jsonl"


def append_delete_feedback(output_dir: Path, deleted_records: list[dict], source: str = "unknown") -> int:
    if not deleted_records:
        return 0
    p = feedback_path(output_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    count = 0
    with p.open("a", encoding="utf-8") as f:
        for raw in deleted_records:
            if not isinstance(raw, dict):
                continue
            row = {
                "time": ts,
                "source": source,
                "action": "delete",
                "record_id": str(raw.get("record_id", "")),
                "display_author": str(raw.get("display_author", "")),
                "dedupe_title": str(raw.get("dedupe_title", "")),
                "duplicate_status": str(raw.get("duplicate_status", "")),
                "duplicate_confidence": int(raw.get("duplicate_confidence", 0) or 0),
                "core_title": str(raw.get("core_title", "")),
                "raw_name": str(raw.get("raw_name", "")),
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def _load_feedback(output_dir: Path) -> list[dict]:
    p = feedback_path(output_dir)
    if not p.exists():
        return []
    rows: list[dict] = []
    try:
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except Exception:
        return []
    return rows


def apply_feedback_learning(records: list[Record], output_dir: Path) -> dict[str, int]:
    rows = _load_feedback(output_dir)
    if not rows:
        return {"rows": 0, "boosted": 0, "annotated": 0}

    key_count: dict[tuple[str, str], int] = defaultdict(int)
    for row in rows:
        if str(row.get("action", "")).strip().lower() != "delete":
            continue
        author = str(row.get("display_author", "")).strip()
        title = str(row.get("dedupe_title", "")).strip()
        status = str(row.get("duplicate_status", "")).strip()
        if not author or not title:
            continue
        if status in {"严格重复", "疑似重复"}:
            key_count[(author, title)] += 1

    boosted = 0
    annotated = 0
    for r in records:
        key = (str(r.display_author or "").strip(), str(r.dedupe_title or "").strip())
        if not key[0] or not key[1]:
            continue
        n = int(key_count.get(key, 0))
        if n < 2:
            continue
        hint = f"历史审核反馈: 同作者同标题删重 {n} 次"
        if hint not in str(r.notes or ""):
            r.notes = f"{r.notes} | {hint}".strip(" |")
            annotated += 1
        if r.duplicate_status == "疑似重复" and int(r.duplicate_confidence or 0) >= 70 and n >= 3:
            r.duplicate_status = "严格重复"
            r.duplicate_confidence = max(85, int(r.duplicate_confidence or 0))
            reason = str(r.duplicate_reason or "")
            if hint not in reason:
                r.duplicate_reason = f"{reason} | {hint}".strip(" |")
            r.manual_review = "是"
            boosted += 1
    if boosted or annotated:
        print(f"[Feedback] rows={len(rows)}, boosted={boosted}, annotated={annotated}")
    return {"rows": len(rows), "boosted": boosted, "annotated": annotated}
