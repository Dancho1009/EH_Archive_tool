from __future__ import annotations

from pathlib import Path


def resolve_policy_path(args, output_dir: Path) -> Path:
    raw = str(getattr(args, "merge_policy_file", "") or "").strip()
    if raw:
        return Path(raw).resolve()
    return (output_dir / "merge_policy.json").resolve()


def apply_manual_author_policy(
    records,
    policy: dict,
    only_new: bool = False,
    frozen_authors: set[str] | None = None,
) -> dict[str, int]:
    """Apply whitelist and circle->author mappings before model merge."""
    frozen_authors = frozen_authors or set()
    whitelist = policy.get("author_whitelist", {}) or {}
    circle_to_author = policy.get("circle_to_author", {}) or {}

    wl_hits = 0
    c2a_hits = 0
    updated = 0
    for r in records:
        if only_new and str(r.ingest_status or "").lower() != "new":
            continue
        if r.display_author and r.display_author in frozen_authors:
            continue

        mapped = ""
        a = str(r.author_std or "").strip()
        c = str(r.circle_std or "").strip()
        if a and a in whitelist:
            mapped = str(whitelist.get(a, "")).strip()
            if mapped:
                wl_hits += 1
        elif (not a) and c and c in circle_to_author:
            mapped = str(circle_to_author.get(c, "")).strip()
            if mapped:
                c2a_hits += 1

        if not mapped:
            continue
        if r.archive_author != mapped:
            updated += 1
        r.archive_author = mapped
        r.display_author = mapped
        if r.author_affinity_status == "无":
            r.author_affinity_status = "规则归并"

    return {"whitelist_hits": wl_hits, "circle_map_hits": c2a_hits, "updated_records": updated}
