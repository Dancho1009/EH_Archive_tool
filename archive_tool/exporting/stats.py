from __future__ import annotations

from collections import defaultdict

from ..models import Record
from .labels import NON_DUP, PENDING, SERIES_NON_DUP, STRICT, SUSPECT


def _is_yes(value: str) -> bool:
    text = str(value or "").strip().lower()
    return text in {"是", "yes", "y", "true", "1", "鏄?"}


def compute_stats(records: list[Record]) -> tuple[dict, list[dict], dict[str, list[Record]]]:
    by_author: dict[str, list[Record]] = defaultdict(list)
    for record in records:
        by_author[record.display_author or PENDING].append(record)

    author_stats: list[dict] = []
    for author, grouped in by_author.items():
        row = {
            "author": author,
            "works": len(grouped),
            "strict_duplicates": sum(1 for x in grouped if x.duplicate_status == STRICT),
            "suspected_duplicates": sum(1 for x in grouped if x.duplicate_status == SUSPECT),
            "series_related_non_duplicates": sum(1 for x in grouped if x.duplicate_status == SERIES_NON_DUP),
            "series_missing_items": sum(1 for x in grouped if _is_yes(x.series_missing)),
            "non_duplicates": sum(1 for x in grouped if x.duplicate_status == NON_DUP),
            "manual_review_items": sum(1 for x in grouped if _is_yes(x.manual_review)),
            "high_risk_items": sum(1 for x in grouped if str(x.risk_level or "").strip() == "high"),
        }
        author_stats.append(row)

    author_stats.sort(
        key=lambda x: (
            0 if str(x["author"]) == PENDING else 1,
            0 if (x["strict_duplicates"] + x["suspected_duplicates"]) > 0 else 1,
            -(x["strict_duplicates"] + x["suspected_duplicates"]),
            -x["works"],
            str(x["author"]),
        )
    )

    stats = {
        "total_records": len(records),
        "author_buckets": len(by_author),
        "known_authors": len({r.archive_author for r in records if r.archive_author}),
        "pending_author_records": sum(1 for r in records if (r.display_author or "") == PENDING),
        "magazine_bucket_records": sum(1 for r in records if (r.display_author or "") == "杂志"),
        "strict_duplicates": sum(1 for r in records if r.duplicate_status == STRICT),
        "suspected_duplicates": sum(1 for r in records if r.duplicate_status == SUSPECT),
        "series_related_non_duplicates": sum(1 for r in records if r.duplicate_status == SERIES_NON_DUP),
        "series_missing_records": sum(1 for r in records if _is_yes(r.series_missing)),
        "series_missing_groups": len(
            {
                (r.display_author, (r.series_key or r.dedupe_title), r.series_missing_numbers)
                for r in records
                if _is_yes(r.series_missing) and r.display_author and (r.series_key or r.dedupe_title)
            }
        ),
        "non_duplicates": sum(1 for r in records if r.duplicate_status == NON_DUP),
        "manual_review_items": sum(1 for r in records if _is_yes(r.manual_review)),
        "high_risk_records": sum(1 for r in records if str(r.risk_level or "").strip() == "high"),
    }
    return stats, author_stats, by_author
