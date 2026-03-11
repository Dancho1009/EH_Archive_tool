from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .processing.parsing import normalize_text


def _norm_name(text: str) -> str:
    return normalize_text(str(text or "")).strip()


def load_policy(path: Path) -> dict[str, Any]:
    """
    Load merge/archive policy.

    Schema (all keys optional):
      - author_whitelist: {"alias": "canonical_author"}
      - author_blacklist: ["name_a", "name_b"]
      - circle_to_author: {"circle_name": "canonical_author"}
      - ambiguous_circles: ["shared_circle_name"]
      - freeze_authors: ["author_or_bucket_name"]
    """
    if not path.exists():
        return {
            "author_whitelist": {},
            "author_blacklist": set(),
            "circle_to_author": {},
            "ambiguous_circles": set(),
            "freeze_authors": set(),
            "_path": str(path),
            "_loaded": False,
        }

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[Policy][WARN] invalid json: {path} error={exc}")
        return {
            "author_whitelist": {},
            "author_blacklist": set(),
            "circle_to_author": {},
            "ambiguous_circles": set(),
            "freeze_authors": set(),
            "_path": str(path),
            "_loaded": False,
        }

    if not isinstance(raw, dict):
        print(f"[Policy][WARN] top-level must be object: {path}")
        raw = {}

    wl_raw = raw.get("author_whitelist", {})
    bl_raw = raw.get("author_blacklist", [])
    c2a_raw = raw.get("circle_to_author", {})
    amb_raw = raw.get("ambiguous_circles", [])
    freeze_raw = raw.get("freeze_authors", [])

    whitelist: dict[str, str] = {}
    if isinstance(wl_raw, dict):
        for k, v in wl_raw.items():
            kk = _norm_name(str(k))
            vv = _norm_name(str(v))
            if kk and vv:
                whitelist[kk] = vv

    blacklist: set[str] = set()
    if isinstance(bl_raw, list):
        for x in bl_raw:
            xx = _norm_name(str(x))
            if xx:
                blacklist.add(xx)

    circle_to_author: dict[str, str] = {}
    if isinstance(c2a_raw, dict):
        for k, v in c2a_raw.items():
            kk = _norm_name(str(k))
            vv = _norm_name(str(v))
            if kk and vv:
                circle_to_author[kk] = vv

    ambiguous_circles: set[str] = set()
    if isinstance(amb_raw, list):
        for x in amb_raw:
            xx = _norm_name(str(x))
            if xx:
                ambiguous_circles.add(xx)

    freeze_authors: set[str] = set()
    if isinstance(freeze_raw, list):
        for x in freeze_raw:
            xx = _norm_name(str(x))
            if xx:
                freeze_authors.add(xx)

    # Ambiguous circles should never be auto-mapped to a single author.
    for c in list(circle_to_author.keys()):
        if c in ambiguous_circles:
            circle_to_author.pop(c, None)

    return {
        "author_whitelist": whitelist,
        "author_blacklist": blacklist,
        "circle_to_author": circle_to_author,
        "ambiguous_circles": ambiguous_circles,
        "freeze_authors": freeze_authors,
        "_path": str(path),
        "_loaded": True,
    }


def is_blacklisted_name(name: str, policy: dict[str, Any]) -> bool:
    n = _norm_name(name)
    return bool(n and n in policy.get("author_blacklist", set()))
