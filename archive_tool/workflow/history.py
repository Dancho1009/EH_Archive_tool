from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path


def append_run_history(
    output_dir: Path,
    input_unique_names: int,
    cache_hit: int,
    mapped: int,
    updated_records: int,
    author_buckets: int,
    parse_new_or_changed: int,
) -> None:
    """Append one run summary row for merge/dedupe tuning."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "运行历史.csv"
    new_header = [
        "time",
        "input_unique_names",
        "author_merge_cache_hit",
        "author_merge_mapped",
        "updated_records",
        "author_buckets",
        "parse_new_or_changed",
    ]
    old_header = [
        "time",
        "input_unique_names",
        "author_merge_mapped",
        "updated_records",
        "author_buckets",
        "parse_new_or_changed",
    ]
    header = new_header
    if path.exists():
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as rf:
                reader = csv.reader(rf)
                first = next(reader, [])
                if first == old_header:
                    header = old_header
                elif first == new_header:
                    header = new_header
        except Exception:
            header = new_header

    new_file = not path.exists()
    with path.open("a", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(header)
        if header == old_header:
            writer.writerow(
                [
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    input_unique_names,
                    mapped,
                    updated_records,
                    author_buckets,
                    parse_new_or_changed,
                ]
            )
        else:
            writer.writerow(
                [
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    input_unique_names,
                    cache_hit,
                    mapped,
                    updated_records,
                    author_buckets,
                    parse_new_or_changed,
                ]
            )
