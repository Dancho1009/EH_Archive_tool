from __future__ import annotations

from collections import defaultdict

from ...models import Record
from .common import detect_gap, to_int


def mark_series_missing(
    records: list[Record],
    freeze_existing: bool = False,
    frozen_authors: set[str] | None = None,
) -> None:
    """Mark probable missing installments within same author+core title groups."""
    frozen_authors = frozen_authors or set()
    grouped: dict[tuple[str, str], list[Record]] = defaultdict(list)
    for r in records:
        key = str(r.series_key or r.dedupe_title or "").strip()
        if not r.display_author or not key:
            continue
        if r.work_type == "magazine":
            continue
        if r.display_author in frozen_authors:
            continue
        grouped[(r.display_author, key)].append(r)

    hit_groups = 0
    for (author, title), group in grouped.items():
        if len(group) < 2:
            continue

        ch_numbers: set[int] = set()
        vol_numbers: set[int] = set()
        for r in group:
            if r.range_start is not None and r.range_end is not None and r.range_start <= r.range_end and (r.range_end - r.range_start) <= 200:
                ch_numbers.update(range(int(r.range_start), int(r.range_end) + 1))
            ch = to_int(r.chapter_no)
            if ch is not None:
                ch_numbers.add(ch)
            vol = to_int(r.volume_no)
            if vol is not None:
                vol_numbers.add(vol)

        ch_missing = detect_gap(ch_numbers)
        vol_missing = detect_gap(vol_numbers)

        index_type = ""
        present_numbers: list[int] = []
        missing_numbers: list[int] = []
        if ch_missing:
            index_type = "chapter"
            present_numbers = sorted(ch_numbers)
            missing_numbers = ch_missing
        elif vol_missing:
            index_type = "volume"
            present_numbers = sorted(vol_numbers)
            missing_numbers = vol_missing
        else:
            continue

        if freeze_existing and not any(str(x.ingest_status or "").lower() == "new" for x in group):
            continue

        hit_groups += 1
        missing_text = ",".join(str(x) for x in missing_numbers)
        present_text = ",".join(str(x) for x in present_numbers)
        confidence = 75
        if len(present_numbers) >= 3:
            confidence += 10
        if len(missing_numbers) == 1:
            confidence += 5
        if len(missing_numbers) >= 4:
            confidence -= 10
        confidence = max(40, min(95, confidence))

        zh_type = "话次" if index_type == "chapter" else "卷次"
        reason = f"已收录{zh_type}: {present_text}；疑似缺失: {missing_text}"
        series_key = f"{author}|{title}"
        for r in group:
            if freeze_existing and str(r.ingest_status or "").lower() != "new":
                continue
            r.series_key = series_key
            r.series_index_type = index_type
            r.series_indices = present_text
            r.series_missing = "是"
            r.series_missing_numbers = missing_text
            r.series_missing_reason = reason
            r.series_missing_confidence = max(r.series_missing_confidence, confidence)
            r.manual_review = "是"
            if reason not in (r.notes or ""):
                r.notes = f"{r.notes} | {reason}".strip(" |")

    print(f"[SeriesMissing][Local] groups={hit_groups}")
