from __future__ import annotations

from collections import defaultdict

from ...models import Record


def mark_suggested_authors(
    records: list[Record],
    freeze_existing: bool = False,
    frozen_authors: set[str] | None = None,
) -> None:
    """Suggest likely author for no-author rows by exact title key."""
    index: dict[str, list[str]] = defaultdict(list)
    frozen_authors = frozen_authors or set()
    for r in records:
        if r.archive_author and r.dedupe_title:
            index[r.dedupe_title].append(r.archive_author)
    for r in records:
        if freeze_existing and str(r.ingest_status or "").lower() != "new":
            continue
        if r.display_author and r.display_author in frozen_authors:
            continue
        if r.archive_author or not r.dedupe_title:
            continue
        cands = index.get(r.dedupe_title, [])
        if cands:
            r.suggested_author = sorted(cands)[0]
            r.author_affinity_status = "疑似归属"
            r.suggested_author_reason = "无作者且标题一致"
            r.suggested_author_confidence = 85
            r.display_author = r.suggested_author
            r.manual_review = "是"
