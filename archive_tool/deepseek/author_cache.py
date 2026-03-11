from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .client import parse_confidence


def load_author_merge_cache(path: Path) -> dict[str, tuple[str, int]]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    items = raw.get("items", {}) if isinstance(raw, dict) else {}
    if not isinstance(items, dict):
        return {}
    out: dict[str, tuple[str, int]] = {}
    for key, value in items.items():
        if not isinstance(value, dict):
            continue
        cache_key = str(key or "").strip()
        canonical = str(value.get("canonical", "")).strip()
        confidence = parse_confidence(value.get("confidence", 0))
        if cache_key and canonical:
            out[cache_key] = (canonical, confidence)
    return out


def save_author_merge_cache(path: Path, mapping: dict[str, tuple[str, int]], model: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    items: dict[str, dict] = {}
    for raw, (canonical, confidence) in mapping.items():
        if not raw or not canonical:
            continue
        items[str(raw)] = {
            "canonical": str(canonical),
            "confidence": int(confidence),
            "model": str(model),
            "updated_at": now,
        }
    payload = {"version": 1, "updated_at": now, "items": items}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
