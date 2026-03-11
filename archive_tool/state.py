from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .models import Record


def load_state(path: Path) -> dict:
    """Load incremental state."""
    if not path.exists():
        return {"entries": {}, "records_by_path": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.setdefault("entries", {})
            data.setdefault("records_by_path", {})
            return data
    except Exception:
        pass
    return {"entries": {}, "records_by_path": {}}


def save_state(path: Path, sigs: dict[str, str], records: list[Record]) -> None:
    """Save incremental state."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"entries": sigs, "records_by_path": {r.full_path: asdict(r) for r in records}}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def restore_record(raw: dict) -> Record:
    """Restore Record from persisted row."""
    fields = Record.__dataclass_fields__.keys()
    return Record(**{k: v for k, v in raw.items() if k in fields})


def reset_runtime(records: list[Record], preserve_existing: bool = False) -> None:
    """Reset derived runtime fields.

    When preserve_existing=True, rows with ingest_status=="existing"
    keep their runtime labels from previous state snapshot.
    """
    for r in records:
        if preserve_existing and str(r.ingest_status or "").lower() == "existing":
            if r.archive_author and r.work_type != "magazine":
                r.display_author = r.archive_author
            elif r.work_type == "magazine":
                r.display_author = "杂志"
            elif not r.display_author:
                r.display_author = "待归档确认"
            continue
        r.author_affinity_status = "无"
        r.suggested_author = ""
        r.suggested_author_reason = ""
        r.suggested_author_confidence = 0
        r.duplicate_status = "不重复"
        r.duplicate_group_id = ""
        r.duplicate_master_id = ""
        r.duplicate_with = ""
        r.duplicate_source_path = ""
        r.duplicate_reason = ""
        r.duplicate_confidence = 0
        r.series_key = ""
        r.series_index_type = ""
        r.series_indices = ""
        r.series_missing = "否"
        r.series_missing_numbers = ""
        r.series_missing_reason = ""
        r.series_missing_confidence = 0
        r.manual_review = "否"
        r.author_sort_key = ""
        r.title_sort_key = ""
        r.risk_level = ""
        r.risk_flags = ""
        r.risk_detail = ""
        if r.archive_author:
            r.display_author = r.archive_author
        elif r.work_type == "magazine":
            r.display_author = "杂志"
        else:
            r.display_author = "待归档确认"
