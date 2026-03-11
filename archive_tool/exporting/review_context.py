from __future__ import annotations

import html
from dataclasses import dataclass
from pathlib import Path

from ..models import Record
from .helpers import series_order_text as _series_order_text
from .helpers import series_title_text as _series_title_text
from .labels import SERIES_NON_DUP, STAT_LABELS, STRICT, SUSPECT


@dataclass
class ReviewRenderContext:
    cards: str
    page_size: int
    author_order: list[str]
    author_to_section: dict[str, str]
    author_to_page: dict[str, int]
    author_stats: list[dict]
    sections: list[str]
    total_authors: int
    total_pages: int


def _build_cards(stats: dict) -> str:
    return "".join(
        [
            f'<div class="card"><div class="k">{html.escape(STAT_LABELS.get(k, k))}</div><div class="v">{v}</div></div>'
            for k, v in [
                ("total_records", stats["total_records"]),
                ("author_buckets", stats["author_buckets"]),
                ("known_authors", stats["known_authors"]),
                ("strict_duplicates", stats["strict_duplicates"]),
                ("suspected_duplicates", stats["suspected_duplicates"]),
                ("series_related_non_duplicates", stats["series_related_non_duplicates"]),
                ("series_missing_records", stats["series_missing_records"]),
                ("high_risk_records", stats.get("high_risk_records", 0)),
            ]
        ]
    )


def _build_sections(
    *,
    by_author: dict[str, list[Record]],
    author_order: list[str],
    author_to_page: dict[str, int],
    author_stat_map: dict[str, dict],
) -> list[str]:
    sections: list[str] = []
    for section_idx, author in enumerate(author_order, 1):
        section_id = f"author-{section_idx}"
        author_stat = author_stat_map.get(author, {})
        strict_n = int(author_stat.get("strict_duplicates", 0) or 0)
        suspect_n = int(author_stat.get("suspected_duplicates", 0) or 0)
        series_n = int(author_stat.get("series_related_non_duplicates", 0) or 0)
        missing_n = int(author_stat.get("series_missing_items", 0) or 0)
        risk_n = int(author_stat.get("high_risk_items", 0) or 0)
        items = []
        for x in by_author[author]:
            row_classes: list[str] = []
            if x.duplicate_status == STRICT:
                row_classes.append("row-dup")
            elif x.duplicate_status == SUSPECT:
                row_classes.append("row-suspect")
            elif x.duplicate_status == SERIES_NON_DUP:
                row_classes.append("row-series")
            if x.series_missing == "是":
                row_classes.append("row-missing")
            if str(x.risk_level or "").strip() == "high":
                row_classes.append("row-risk")
            cls = " ".join(row_classes)
            duplicate_reason = str(x.duplicate_reason or "").strip()
            duplicate_conf = str(x.duplicate_confidence or "").strip() if int(x.duplicate_confidence or 0) > 0 else ""
            series_reason = str(x.series_missing_reason or "").strip()
            series_conf = str(x.series_missing_confidence or "").strip() if int(x.series_missing_confidence or 0) > 0 else ""
            risk_detail = str(x.risk_detail or "").strip()
            explain = " | ".join(
                part
                for part in [
                    duplicate_reason,
                    f"重复置信度:{duplicate_conf}" if duplicate_conf else "",
                    series_reason,
                    f"缺失置信度:{series_conf}" if series_conf else "",
                    risk_detail,
                ]
                if part
            )
            items.append(
                f"""
                <tr
                  class=\"{cls}\"
                  title=\"{html.escape(explain)}\"
                  data-record-id=\"{html.escape(x.record_id)}\"
                  data-dup-status=\"{html.escape(x.duplicate_status)}\"
                  data-dup-group=\"{html.escape(x.duplicate_group_id)}\"
                  data-master-id=\"{html.escape(x.duplicate_master_id)}\"
                >
                  <td>
                    <input
                      type=\"checkbox\"
                      class=\"row-select\"
                      data-section=\"{section_id}\"
                      data-path=\"{html.escape(x.full_path)}\"
                      data-parent-path=\"{html.escape(x.parent_path)}\"
                    />
                  </td>
                  <td>{html.escape(x.record_id)}</td>
                  <td>{html.escape(x.author_raw)}</td>
                  <td>{html.escape(x.circle_raw)}</td>
                  <td>{html.escape(x.raw_name)}</td>
                  <td>{html.escape(_series_title_text(x))}</td>
                  <td>{html.escape(_series_order_text(x))}</td>
                  <td>{html.escape(x.size_text or "0 B")}</td>
                  <td>{html.escape(x.page_count_text or "")}</td>
                  <td>{html.escape(x.risk_level or "")}</td>
                  <td>{html.escape(x.risk_flags or "")}</td>
                  <td>{html.escape(risk_detail)}</td>
                  <td>{html.escape(x.duplicate_status)}</td>
                  <td>{html.escape(x.duplicate_with)}</td>
                  <td>{html.escape(duplicate_reason)}</td>
                  <td>{html.escape(duplicate_conf)}</td>
                  <td>{html.escape(x.series_missing)}</td>
                  <td>{html.escape(x.series_missing_numbers)}</td>
                  <td>{html.escape(series_reason)}</td>
                  <td>{html.escape(series_conf)}</td>
                </tr>
                """
            )
        items_html = "".join(items)
        items_blob = items_html.replace("</script>", "<\\/script>")
        sections.append(
            f"""
            <section
              id=\"{section_id}\"
              class=\"panel\"
              data-section=\"{section_id}\"
              data-author=\"{html.escape(author)}\"
              data-author-index=\"{section_idx - 1}\"
              data-page=\"{author_to_page.get(author, 0)}\"
              data-strict=\"{strict_n}\"
              data-suspect=\"{suspect_n}\"
              data-series=\"{series_n}\"
              data-missing=\"{missing_n}\"
              data-risk=\"{risk_n}\"
            >
              <div class=\"section-head\">
                <h2><span class=\"author-name\">{html.escape(author)}</span> <small class=\"works-count\">({len(by_author[author])} 作品)</small></h2>
                <div class=\"section-head-right\">
                  <div class=\"dup-summary\">
                    <span class=\"dup-chip chip-dup\" data-chip=\"strict\">严格 {strict_n}</span>
                    <span class=\"dup-chip chip-suspect\" data-chip=\"suspect\">疑似 {suspect_n}</span>
                    <span class=\"dup-chip chip-series\" data-chip=\"series\">系列相关 {series_n}</span>
                    <span class=\"dup-chip chip-missing\" data-chip=\"missing\">缺失 {missing_n}</span>
                    <span class=\"dup-chip chip-risk\" data-chip=\"risk\">风险 {risk_n}</span>
                  </div>
                  <button type=\"button\" class=\"btn-op section-toggle\" data-section=\"{section_id}\" data-open=\"0\">展开</button>
                </div>
              </div>
              <div class=\"section-body\">
                <div class=\"section-actions\" data-section=\"{section_id}\">
                  <button type=\"button\" class=\"btn-op act-select-all\" data-section=\"{section_id}\">全选</button>
                  <button type=\"button\" class=\"btn-op act-clear\" data-section=\"{section_id}\">清空</button>
                  <button type=\"button\" class=\"btn-op act-invert\" data-section=\"{section_id}\">反选</button>
                  <button type=\"button\" class=\"btn-op act-open-file\" data-section=\"{section_id}\">打开选中项</button>
                  <button type=\"button\" class=\"btn-op act-open-parent\" data-section=\"{section_id}\">打开所在目录</button>
                  <button type=\"button\" class=\"btn-op act-copy\" data-section=\"{section_id}\">复制选中路径</button>
                  <button type=\"button\" class=\"btn-op act-export\" data-section=\"{section_id}\">导出选中路径</button>
                  <button type=\"button\" class=\"btn-op btn-danger act-delete\" data-section=\"{section_id}\">删除选中</button>
                  <span class=\"sel-count\" id=\"count-{section_id}\">已选 0</span>
                </div>
                <div class=\"table-wrap records-wrap\">
                  <table class=\"records-table\">
                    <thead>
                      <tr>
                        <th>选</th>
                        <th>记录ID</th>
                        <th>原始作者</th>
                        <th>原始社团</th>
                        <th>原始名称</th>
                        <th>核心标题/系列标题</th>
                        <th>系列序号</th>
                        <th>体积</th>
                        <th>页数</th>
                        <th>风险等级</th>
                        <th>风险标签</th>
                        <th>风险说明</th>
                        <th>重复状态</th>
                        <th>重复来源</th>
                        <th>重复说明</th>
                        <th>重复置信度</th>
                        <th>系列缺失</th>
                        <th>缺失序号</th>
                        <th>缺失说明</th>
                        <th>缺失置信度</th>
                      </tr>
                    </thead>
                    <tbody id=\"tbody-{section_id}\"></tbody>
                  </table>
                </div>
              </div>
              <script type=\"text/plain\" id=\"tpl-{section_id}\">{items_blob}</script>
            </section>
            """
        )
    return sections


def build_review_context(
    *,
    stats: dict,
    author_stats: list[dict],
    by_author: dict[str, list[Record]],
    author_order: list[str],
    output_dir: Path,
    page_size: int,
) -> ReviewRenderContext:
    author_to_section = {author: f"author-{idx}" for idx, author in enumerate(author_order, 1)}
    author_to_page = {author: idx // page_size for idx, author in enumerate(author_order)}
    author_stat_map = {x["author"]: x for x in author_stats}
    sections = _build_sections(
        by_author=by_author,
        author_order=author_order,
        author_to_page=author_to_page,
        author_stat_map=author_stat_map,
    )
    total_authors = len(author_order)
    total_pages = max(1, (total_authors + page_size - 1) // page_size)
    return ReviewRenderContext(
        cards=_build_cards(stats),
        page_size=page_size,
        author_order=author_order,
        author_to_section=author_to_section,
        author_to_page=author_to_page,
        author_stats=author_stats,
        sections=sections,
        total_authors=total_authors,
        total_pages=total_pages,
    )
