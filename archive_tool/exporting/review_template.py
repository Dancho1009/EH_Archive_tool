from __future__ import annotations

from .labels import AUTHOR_STAT_LABELS
from .review_script import REVIEW_PAGE_SCRIPT
from .review_style import REVIEW_PAGE_STYLE


def render_review_page(
    *,
    page_index: int,
    total_pages: int,
    page_size: int,
    total_authors: int,
    default_page_size: int,
    cards: str,
    author_stat_rows: str,
    pager_html: str,
    sections_html: str,
) -> str:
    return f"""
    <!doctype html>
    <html lang="zh-CN">
    <head>
      <meta charset="utf-8" />
      <title>作品归档审核页 - 第 {page_index + 1}/{total_pages} 页</title>
      <style>
{REVIEW_PAGE_STYLE}
      </style>
    </head>
    <body>
      <main
        data-page-size="{page_size}"
        data-current-page="{page_index}"
        data-total-pages="{total_pages}"
        data-total-authors="{total_authors}"
        data-default-size="{default_page_size}"
      >
        <h1>作品归档审核页<small id="page-info">第 {page_index + 1}/{total_pages} 页</small></h1>
        <section class="panel">
          <h2>统计概览</h2>
          <div class="grid">{cards}</div>
        </section>
        <section class="panel">
          <h2>作者统计</h2>
          <div class="author-tools">
            <input id="author-search" class="author-search" type="text" placeholder="搜索作者名（全局）" />
          </div>
          <div class="table-wrap author-stat-wrap">
            <table>
              <thead>
                <tr>
                  <th>{AUTHOR_STAT_LABELS["author"]}</th>
                  <th>{AUTHOR_STAT_LABELS["works"]}</th>
                  <th>{AUTHOR_STAT_LABELS["strict_duplicates"]}</th>
                  <th>{AUTHOR_STAT_LABELS["suspected_duplicates"]}</th>
                  <th>{AUTHOR_STAT_LABELS["series_related_non_duplicates"]}</th>
                  <th>{AUTHOR_STAT_LABELS["series_missing_items"]}</th>
                  <th>{AUTHOR_STAT_LABELS.get("high_risk_items", "高风险待审")}</th>
                  <th>{AUTHOR_STAT_LABELS["non_duplicates"]}</th>
                </tr>
              </thead>
              <tbody>
                {author_stat_rows}
              </tbody>
            </table>
          </div>
        </section>
        {pager_html}
        {sections_html}
        {pager_html}
      </main>
      <div id="copy-tip"></div>
      <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
      <script>
{REVIEW_PAGE_SCRIPT}
      </script>
    </body>
    </html>
    """
