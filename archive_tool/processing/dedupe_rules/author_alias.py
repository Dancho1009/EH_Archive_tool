from __future__ import annotations

from collections import Counter, defaultdict

from ...models import Record
from .common import normalized_gid


def _has_non_ascii(text: str) -> int:
    return 1 if any(ord(ch) > 127 for ch in text or "") else 0


def _choose_canonical_name(names: list[str]) -> str:
    counter = Counter([n for n in names if n])
    if not counter:
        return ""
    ranked = sorted(
        counter.items(),
        key=lambda kv: (
            -kv[1],  # frequency
            -_has_non_ascii(kv[0]),  # prefer JP/CJK style labels when tied
            -len(kv[0]),
            kv[0].lower(),
        ),
    )
    return ranked[0][0]


def normalize_author_alias_by_gid(
    records: list[Record],
    freeze_existing: bool = False,
    frozen_authors: set[str] | None = None,
) -> None:
    """
    Same gid means same gallery.
    If same gid has multiple author aliases (JP / romaji), collapse to one canonical author.
    """
    frozen_authors = frozen_authors or set()
    by_gid: dict[str, list[Record]] = defaultdict(list)
    for r in records:
        gid = normalized_gid(r)
        if not gid:
            continue
        by_gid[gid].append(r)

    merged_groups = 0
    updated = 0
    for gid, group in by_gid.items():
        if len(group) < 2:
            continue
        names = [str(x.archive_author or x.author_std or "").strip() for x in group]
        uniq = sorted({x for x in names if x})
        if len(uniq) < 2:
            continue
        canonical = _choose_canonical_name(names)
        if not canonical:
            continue
        changed_any = False
        for r in group:
            if frozen_authors and r.display_author in frozen_authors:
                continue
            if freeze_existing and str(r.ingest_status or "").lower() != "new":
                continue
            if str(r.archive_author or "").strip() != canonical:
                r.archive_author = canonical
                r.display_author = canonical
                r.author_affinity_status = "gid_alias_merge"
                if "GID别名归并" not in (r.notes or ""):
                    r.notes = f"{r.notes} | GID别名归并: {gid}".strip(" |")
                updated += 1
                changed_any = True
        if changed_any:
            merged_groups += 1
    if merged_groups or updated:
        print(f"[AuthorAlias][GID] groups={merged_groups}, updated_records={updated}")
