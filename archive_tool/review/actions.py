from __future__ import annotations

import csv
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from ..exporting.pipeline import apply_exports
from ..state import restore_record
from ..workflow.feedback import append_delete_feedback


def _load_state(path: Path) -> dict:
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


def _save_state(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_path(text: str) -> str:
    try:
        return str(Path(text).resolve())
    except Exception:
        return ""


def _path_hit(target: str, root: str) -> bool:
    t = str(target or "")
    r = str(root or "")
    if not t or not r:
        return False
    if t == r:
        return True
    return t.startswith(r + os.sep)


def _delete_path(path: Path) -> tuple[bool, str]:
    try:
        if not path.exists():
            return False, "missing"
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _update_state_after_delete(state_file: Path, deleted_paths: list[str]) -> dict[str, int]:
    state = _load_state(state_file)
    entries = state.get("entries", {})
    records_by_path = state.get("records_by_path", {})

    removed_entries = 0
    removed_records = 0
    delete_roots = [p for p in deleted_paths if p]

    for key in list(entries.keys()):
        if any(_path_hit(key, d) for d in delete_roots):
            entries.pop(key, None)
            removed_entries += 1

    for key in list(records_by_path.keys()):
        if any(_path_hit(key, d) for d in delete_roots):
            records_by_path.pop(key, None)
            removed_records += 1

    _save_state(state_file, state)
    return {"removed_entries": removed_entries, "removed_records": removed_records}


def _collect_records_from_state(state_file: Path, target_paths: list[str]) -> list[dict]:
    state = _load_state(state_file)
    records_by_path = state.get("records_by_path", {})
    out: list[dict] = []
    for key, row in records_by_path.items():
        if any(_path_hit(str(key), d) for d in target_paths):
            if isinstance(row, dict):
                out.append(dict(row))
    return out


def _update_result_json_after_delete(output_dir: Path, deleted_paths: list[str]) -> int:
    result_json = output_dir / "作品归档结果.json"
    if not result_json.exists():
        return 0
    try:
        rows = json.loads(result_json.read_text(encoding="utf-8"))
    except Exception:
        return 0
    if not isinstance(rows, list):
        return 0

    before = len(rows)
    kept = []
    for row in rows:
        full_path = normalize_path(str((row or {}).get("full_path", "")))
        if full_path and any(_path_hit(full_path, d) for d in deleted_paths):
            continue
        kept.append(row)
    if len(kept) != before:
        result_json.write_text(json.dumps(kept, ensure_ascii=False, indent=2), encoding="utf-8")
    return before - len(kept)


def _quick_reexport_from_state(output_dir: Path, state_file: Path) -> dict[str, int | bool | str]:
    """Fast re-export using state snapshot without rescanning roots."""
    state = _load_state(state_file)
    entries = state.get("entries", {})
    records_by_path = state.get("records_by_path", {})
    missing_keys: list[str] = []
    records = []
    for key, raw in list(records_by_path.items()):
        p = Path(str(key))
        if not p.exists():
            missing_keys.append(str(key))
            continue
        try:
            records.append(restore_record(raw))
        except Exception:
            missing_keys.append(str(key))

    if missing_keys:
        for k in missing_keys:
            records_by_path.pop(k, None)
            entries.pop(k, None)
        _save_state(state_file, state)

    try:
        apply_exports(records, output_dir.resolve(), history_keep=0)
        return {
            "ok": True,
            "records": len(records),
            "removed_stale": len(missing_keys),
        }
    except Exception as exc:
        return {
            "ok": False,
            "records": len(records),
            "removed_stale": len(missing_keys),
            "error": str(exc),
        }


def _append_operation_log(output_dir: Path, row: dict) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "操作日志.csv"
    jsonl_path = output_dir / "操作日志.jsonl"
    # JSONL for detailed payload.
    with jsonl_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    # CSV for quick human scan.
    headers = [
        "time",
        "action",
        "source",
        "requested",
        "deleted",
        "missing",
        "failed",
        "state_removed_entries",
        "state_removed_records",
        "result_json_removed",
        "reexport_ok",
        "reexport_records",
        "reexport_removed_stale",
        "message",
    ]
    new_file = not csv_path.exists()
    with csv_path.open("a", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(headers)
        w.writerow(
            [
                row.get("time", ""),
                row.get("action", ""),
                row.get("source", ""),
                row.get("requested", 0),
                row.get("deleted", 0),
                row.get("missing", 0),
                row.get("failed", 0),
                row.get("state_removed_entries", 0),
                row.get("state_removed_records", 0),
                row.get("result_json_removed", 0),
                row.get("reexport_ok", False),
                row.get("reexport_records", 0),
                row.get("reexport_removed_stale", 0),
                row.get("message", ""),
            ]
        )


def delete_and_sync(
    paths: list[str],
    output_dir: Path,
    state_file: Path,
    source: str = "unknown",
    quick_reexport: bool = True,
) -> dict:
    norm_paths = sorted({normalize_path(str(p or "")) for p in paths if str(p or "").strip()})
    deleted: list[str] = []
    missing: list[str] = []
    failed: list[dict] = []
    for p in norm_paths:
        ok, err = _delete_path(Path(p))
        if ok:
            deleted.append(p)
        elif err == "missing":
            missing.append(p)
        else:
            failed.append({"path": p, "error": err})

    state_sync = {"removed_entries": 0, "removed_records": 0}
    removed_from_result_json = 0
    reexport_result: dict[str, int | bool | str] = {"ok": False, "records": 0, "removed_stale": 0}
    feedback_written = 0
    if deleted:
        deleted_records = _collect_records_from_state(state_file.resolve(), deleted)
        feedback_written = append_delete_feedback(output_dir.resolve(), deleted_records, source=source)
        state_sync = _update_state_after_delete(state_file.resolve(), deleted)
        removed_from_result_json = _update_result_json_after_delete(output_dir.resolve(), deleted)
        if quick_reexport:
            reexport_result = _quick_reexport_from_state(output_dir.resolve(), state_file.resolve())

    payload = {
        "ok": True,
        "deleted": deleted,
        "missing": missing,
        "failed": failed,
        "state_sync": state_sync,
        "result_json_removed": removed_from_result_json,
        "reexport": reexport_result,
        "feedback_written": feedback_written,
        "message": "删除已执行，且已触发快速重导出。" if bool(reexport_result.get("ok")) else "删除已执行；快速重导出失败，建议手动跑一次增量。",
    }
    _append_operation_log(
        output_dir.resolve(),
        {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": "delete",
            "source": source,
            "requested": len(norm_paths),
            "deleted": len(deleted),
            "missing": len(missing),
            "failed": len(failed),
            "state_removed_entries": int(state_sync.get("removed_entries", 0)),
            "state_removed_records": int(state_sync.get("removed_records", 0)),
            "result_json_removed": int(removed_from_result_json),
            "reexport_ok": bool(reexport_result.get("ok", False)),
            "reexport_records": int(reexport_result.get("records", 0) or 0),
            "reexport_removed_stale": int(reexport_result.get("removed_stale", 0) or 0),
            "message": str(payload.get("message", "")),
            "failed_items": failed,
            "deleted_paths": deleted,
            "missing_paths": missing,
        },
    )
    return payload
