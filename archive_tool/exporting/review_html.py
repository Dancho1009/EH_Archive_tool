from __future__ import annotations

import html
from pathlib import Path

from ..models import Record
from .review_context import build_review_context as _build_review_context
from .helpers import (
    build_review_pager as _build_review_pager,
    review_page_filename as _review_page_filename,
    review_main_filename as _review_main_filename,
    DEFAULT_PAGE_SIZE,
    PAGE_SIZE_OPTIONS,
)
from .labels import REVIEW_MAIN_HTML
from .review_template import render_review_page as _render_review_page


def _cleanup_extra_review_artifacts(output_dir: Path) -> None:
    # remove legacy multi-page folders and extra main files
    for path in output_dir.glob("作品归档审核页_pages*"):
        if path.is_dir():
            for old in path.glob("*.html"):
                try:
                    old.unlink()
                except OSError:
                    pass
            try:
                path.rmdir()
            except OSError:
                pass
    for size in PAGE_SIZE_OPTIONS:
        if size == DEFAULT_PAGE_SIZE:
            continue
        extra = output_dir / f"作品归档审核页_每页{size}.html"
        if extra.exists():
            try:
                extra.unlink()
            except OSError:
                pass


def export_review_html(
    *,
    stats: dict,
    author_stats: list[dict],
    by_author: dict[str, list[Record]],
    author_order: list[str],
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    page_size = DEFAULT_PAGE_SIZE

    ctx = _build_review_context(
        stats=stats,
        author_stats=author_stats,
        by_author=by_author,
        author_order=author_order,
        output_dir=output_dir,
        page_size=page_size,
    )
    cards = ctx.cards
    author_to_section = ctx.author_to_section
    author_to_page = ctx.author_to_page
    sections = ctx.sections
    total_authors = ctx.total_authors
    total_pages = ctx.total_pages

    author_stat_rows = "".join(
        [
            f"""
            <tr
              class=\"author-stat-row\"
              data-author=\"{html.escape(str(x["author"]).lower())}\"
              data-section=\"{author_to_section.get(x["author"], "")}\"
              data-index=\"{idx}\"
              data-page=\"{author_to_page.get(x["author"], 0)}\"
              data-strict=\"{x["strict_duplicates"]}\"
              data-suspect=\"{x["suspected_duplicates"]}\"
              data-series=\"{x["series_related_non_duplicates"]}\"
              data-missing=\"{x["series_missing_items"]}\"
              data-risk=\"{x.get("high_risk_items", 0)}\"
            >
              <td>
                <a class=\"author-jump\" href=\"#{author_to_section.get(x["author"], "")}\">
                  {html.escape(str(x["author"]))}
                </a>
              </td>
              <td>{x["works"]}</td>
              <td>{x["strict_duplicates"]}</td>
              <td>{x["suspected_duplicates"]}</td>
              <td>{x["series_related_non_duplicates"]}</td>
              <td>{x["series_missing_items"]}</td>
              <td>{x.get("high_risk_items", 0)}</td>
              <td>{x["non_duplicates"]}</td>
            </tr>
            """
            for idx, x in enumerate(author_stats)
        ]
    )
    sections_html = "".join(sections)
    pager_html = _build_review_pager(0, total_pages, total_authors, page_size)

    page = _render_review_page(
        page_index=0,
        total_pages=total_pages,
        page_size=page_size,
        total_authors=total_authors,
        default_page_size=DEFAULT_PAGE_SIZE,
        cards=cards,
        author_stat_rows=author_stat_rows,
        pager_html=pager_html,
        sections_html=sections_html,
    )
    out_name = _review_page_filename()
    out_path = output_dir / out_name
    out_path.write_text(page, encoding="utf-8")

    _cleanup_extra_review_artifacts(output_dir)
    return output_dir / REVIEW_MAIN_HTML
