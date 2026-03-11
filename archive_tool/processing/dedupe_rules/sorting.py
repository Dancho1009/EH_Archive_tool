from __future__ import annotations

from ...models import Record


def finalize_sort_keys(records: list[Record]) -> None:
    """Fill sort key fields."""
    records.sort(key=lambda r: (r.display_author, r.dedupe_title, r.volume_no, r.chapter_no, r.raw_name))
    for r in records:
        r.author_sort_key = r.display_author
        r.title_sort_key = f"{r.dedupe_title}|{r.volume_no}|{r.chapter_no}"
