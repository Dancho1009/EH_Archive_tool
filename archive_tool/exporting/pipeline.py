from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from ..models import Record
from .excel import export_excel as _export_excel
from .helpers import reorder_headers as _reorder_headers
from .history import save_history_snapshot as _save_history_snapshot
from .json_export import export_json_outputs as _export_json_outputs
from .labels import PENDING
from .review_html import export_review_html as _export_review_html
from .stats import compute_stats as _compute_stats


def apply_exports(records: list[Record], output_dir: Path, history_keep: int = 3) -> None:
    """Write Excel + HTML + JSON outputs with summary statistics."""
    output_dir.mkdir(parents=True, exist_ok=True)

    stats, author_stats, by_author = _compute_stats(records)
    author_order = [x["author"] for x in author_stats]
    author_rank = {author: i for i, author in enumerate(author_order)}

    records.sort(
        key=lambda r: (
            author_rank.get(r.display_author or PENDING, 10**9),
            r.dedupe_title,
            r.volume_no,
            r.chapter_no,
            r.raw_name,
        )
    )
    for r in records:
        r.author_sort_key = r.display_author
        r.title_sort_key = f"{r.dedupe_title}|{r.volume_no}|{r.chapter_no}"

    rows = [asdict(r) for r in records]
    headers = _reorder_headers(list(rows[0].keys()) if rows else [])

    # ---- Excel ----
    saved_excel_path = _export_excel(
        rows=rows,
        headers=headers,
        stats=stats,
        author_stats=author_stats,
        output_dir=output_dir,
    )

    # ---- HTML ----
    review_html_path = _export_review_html(
        stats=stats,
        author_stats=author_stats,
        by_author=by_author,
        author_order=author_order,
        output_dir=output_dir,
    )

    # ---- JSON ----
    json_result_path, json_stats_path = _export_json_outputs(
        rows=rows,
        stats=stats,
        author_stats=author_stats,
        output_dir=output_dir,
    )
    _save_history_snapshot(
        output_dir,
        history_keep,
        [
            saved_excel_path,
            review_html_path,
            json_result_path,
            json_stats_path,
        ],
    )
