from __future__ import annotations

import html
import unicodedata

from ..models import Record
from .labels import REVIEW_MAIN_HTML

DEFAULT_PAGE_SIZE = 50
PAGE_SIZE_OPTIONS = list(range(10, 101, 10))
if DEFAULT_PAGE_SIZE not in PAGE_SIZE_OPTIONS:
    PAGE_SIZE_OPTIONS.append(DEFAULT_PAGE_SIZE)
PAGE_SIZE_OPTIONS = sorted(set(PAGE_SIZE_OPTIONS))


def review_main_filename() -> str:
    return REVIEW_MAIN_HTML


def review_page_filename() -> str:
    return REVIEW_MAIN_HTML


def build_review_pager(
    page_index: int,
    total_pages: int,
    total_items: int,
    page_size: int,
) -> str:
    # Initial pager HTML (JS will re-render based on filters and page size).
    start = page_index * page_size + 1 if total_items else 0
    end = min(total_items, (page_index + 1) * page_size) if total_items else 0

    pages = {0, max(0, total_pages - 1)}
    for p in range(max(0, page_index - 2), min(total_pages, page_index + 3)):
        pages.add(p)
    ordered = sorted(pages)

    parts: list[str] = []
    if total_pages <= 1:
        parts.append('<span class="pager-btn disabled">|&lt;</span>')
        parts.append('<span class="pager-btn disabled">&lt;</span>')
        parts.append('<span class="pager-btn disabled">&gt;</span>')
        parts.append('<span class="pager-btn disabled">&gt;|</span>')
    else:
        if page_index > 0:
            parts.append('<a class="pager-btn" href="?p=1">|&lt;</a>')
            parts.append(f'<a class="pager-btn" href="?p={page_index}">&lt;</a>')
        else:
            parts.append('<span class="pager-btn disabled">|&lt;</span>')
            parts.append('<span class="pager-btn disabled">&lt;</span>')
        prev = None
        for p in ordered:
            if prev is not None and p - prev > 1:
                parts.append('<span class="pager-ellipsis">...</span>')
            cls = "pager-num current" if p == page_index else "pager-num"
            parts.append(f'<a class="{cls}" href="?p={p + 1}">{p + 1}</a>')
            prev = p
        if page_index < total_pages - 1:
            parts.append(f'<a class="pager-btn" href="?p={page_index + 2}">&gt;</a>')
            parts.append(f'<a class="pager-btn" href="?p={total_pages}">&gt;|</a>')
        else:
            parts.append('<span class="pager-btn disabled">&gt;</span>')
            parts.append('<span class="pager-btn disabled">&gt;|</span>')

    size_options = "".join(
        [
            f'<option value="{size}"{" selected" if size == page_size else ""}>{size}</option>'
            for size in PAGE_SIZE_OPTIONS
        ]
    )

    return f"""
    <div class="pager-wrap">
      <div class="pager-meta">{start} - {end} / {total_items}</div>
      <div class="pager-right">
        <div class="pager-filter">
          <label>作者筛选</label>
          <select class="author-type-filter">
            <option value="all">全部</option>
            <option value="strict">有严格重复</option>
            <option value="suspect">有疑似重复</option>
            <option value="series">有系列相关</option>
            <option value="missing">有系列缺失</option>
            <option value="risk">有高风险待审</option>
          </select>
        </div>
        <div class="pager-filter">
          <label>每页作者数</label>
          <select class="page-size-filter" data-current-size="{page_size}">
            {size_options}
          </select>
        </div>
        <div class="pager">{''.join(parts)}</div>
      </div>
    </div>
    """


def reorder_headers(headers: list[str]) -> list[str]:
    if not headers:
        return headers
    first = headers[0]
    rest = [h for h in headers[1:] if h not in {"author_raw", "circle_raw"}]
    ordered = [first]
    if "author_raw" in headers:
        ordered.append("author_raw")
    if "circle_raw" in headers:
        ordered.append("circle_raw")
    ordered.extend(rest)
    return ordered


def display_width(text: str) -> int:
    width = 0
    for ch in str(text or ""):
        if unicodedata.east_asian_width(ch) in {"F", "W", "A"}:
            width += 2
        else:
            width += 1
    return width


def set_auto_width_all(ws) -> None:
    for col in ws.iter_cols(min_row=1, max_row=ws.max_row, min_col=1, max_col=ws.max_column):
        max_len = 0
        for cell in col:
            max_len = max(max_len, display_width(str(cell.value or "")))
        ws.column_dimensions[col[0].column_letter].width = max(10, min(100, max_len + 2))


def series_title_text(record: Record) -> str:
    return str(record.core_title or record.dedupe_title or record.title_raw or "").strip()


def series_order_text(record: Record) -> str:
    chapter_no = str(record.chapter_no or "").strip()
    volume_no = str(record.volume_no or "").strip()
    if record.range_start is not None and record.range_end is not None:
        return f"{record.range_start}-{record.range_end}"
    if chapter_no:
        return f"第{chapter_no}话"
    if volume_no:
        return f"第{volume_no}卷"
    return str(record.series_indices or "").strip()
