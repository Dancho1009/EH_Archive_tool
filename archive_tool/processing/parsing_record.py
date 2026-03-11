from __future__ import annotations

import re
from pathlib import Path

from ..models import Record
from .parsing_meta import (
    dir_size_bytes,
    ehviewer_sidecar,
    human_size,
    parse_ehviewer_page_count,
    parse_ehviewer_page_count_from_zip,
)
from .parsing_text import (
    CHAPTER_RE,
    extract_series_suffix,
    FRONT_BLOCK_RE,
    LEADING_PAREN_RE,
    PAREN_RE,
    PREFIX_ID_RE,
    RANGE_RE,
    TRAILING_TAG_RE,
    VOLUME_RE,
    YEAR_RE,
    classify_tag,
    is_group_like,
    normalize_key,
    normalize_series_key,
    normalize_text,
)


def parse_record(path: Path, rid: str) -> Record:
    rec = Record(rid, path.name, str(path.resolve()), str(path.resolve().parent), path.is_dir(), "" if path.is_dir() else path.suffix.lower())
    try:
        size_bytes = dir_size_bytes(path) if rec.is_dir else path.stat().st_size
    except OSError:
        size_bytes = 0
    rec.size_bytes = int(size_bytes)
    rec.size_text = human_size(rec.size_bytes)
    if rec.is_dir:
        rec.page_count = parse_ehviewer_page_count(ehviewer_sidecar(path, True))
    elif rec.extension == ".zip":
        rec.page_count = parse_ehviewer_page_count_from_zip(path)
    else:
        rec.page_count = parse_ehviewer_page_count(ehviewer_sidecar(path, False))
    rec.page_count_text = str(rec.page_count) if rec.page_count > 0 else ""
    name = normalize_text(path.name if path.is_dir() else path.stem)

    m = PREFIX_ID_RE.match(name)
    if m:
        rec.prefix_id = m.group("prefix")
        name = name[m.end() :].strip()

    leading_events: list[str] = []
    while True:
        m = LEADING_PAREN_RE.match(name)
        if not m:
            break
        event_text = normalize_text(m.group("content"))
        if event_text:
            leading_events.append(event_text)
        name = name[m.end() :].strip()

    front_tags: list[str] = []
    front_title_candidates: list[str] = []
    while True:
        m = FRONT_BLOCK_RE.match(name)
        if not m:
            break
        block = normalize_text(m.group("sq") or m.group("cn") or "")
        name = name[m.end() :].strip()

        if is_group_like(block):
            front_tags.append(block)
            continue

        mm = re.match(r"^(?P<circle>.+?)\s*\((?P<author>.+?)\)$", block)
        if mm and not rec.author_raw:
            rec.author_raw = normalize_text(mm.group("author"))
            rec.circle_raw = normalize_text(mm.group("circle"))
        elif not rec.author_raw:
            rec.author_raw = block
        else:
            front_tags.append(block)
            front_title_candidates.append(block)

    tags: list[str] = []
    while True:
        m = TRAILING_TAG_RE.search(name)
        if not m:
            break
        tags.append(normalize_text(m.group("sq") or m.group("cn") or ""))
        name = name[: m.start()].strip()
    tags.reverse()
    tags = front_tags + tags

    langs: list[str] = []
    vers: list[str] = []
    groups: list[str] = []
    stats: list[str] = []
    for t in tags:
        k = classify_tag(t)
        if k == "language":
            langs.append(t)
        elif k == "version":
            vers.append(t)
        elif k == "status":
            stats.append(t)
        elif k == "group":
            groups.append(t)

    rec.language_tags = " | ".join(langs)
    rec.version_tags = " | ".join(vers)
    rec.group_tag = " | ".join(groups)
    rec.status_tags = " | ".join(stats)

    paren_vals = [normalize_text(x) for x in PAREN_RE.findall(name) if normalize_text(x)]
    paren_vals = leading_events + paren_vals
    for v in paren_vals:
        if YEAR_RE.search(v) and ("月号" in v or "vol." in v.lower() or "comic" in v.lower()):
            rec.source_info = v if not rec.source_info else f"{rec.source_info} | {v}"
        else:
            rec.ip_info = v if not rec.ip_info else f"{rec.ip_info} | {v}"
    name = normalize_text(PAREN_RE.sub("", name))
    if not name and front_title_candidates:
        name = normalize_text(front_title_candidates[0])
    rec.title_raw = name

    m = RANGE_RE.search(name)
    if m:
        rec.range_start, rec.range_end = int(m.group("start")), int(m.group("end"))
        name = normalize_text(name.replace(m.group(0), " "))
    m = CHAPTER_RE.search(name)
    if m:
        rec.chapter_no = m.group("num")
        name = normalize_text(name.replace(m.group(0), " "))
    m = VOLUME_RE.search(name)
    if m and not rec.chapter_no:
        rec.volume_no = m.group("num")
        name = normalize_text(name[: m.start()])

    series_title_hint = ""
    if not rec.chapter_no and not rec.volume_no and rec.range_start is None and rec.range_end is None:
        series_title_hint, auto_no = extract_series_suffix(name)
        if auto_no:
            rec.volume_no = auto_no
            name = series_title_hint

    rec.core_title = normalize_text(name)
    rec.dedupe_title = normalize_key(rec.core_title)
    rec.series_key = normalize_series_key(series_title_hint or rec.core_title) or rec.dedupe_title
    rec.author_std = normalize_text(rec.author_raw)
    rec.circle_std = normalize_text(rec.circle_raw)
    rec.archive_author = rec.author_std or rec.circle_std
    rec.display_author = rec.archive_author or "待归档确认"

    low = rec.raw_name.lower()
    if "comic " in low and YEAR_RE.search(rec.raw_name):
        rec.work_type = "magazine"
        rec.display_author = rec.archive_author or "杂志"
    else:
        rec.work_type = "author_work" if rec.core_title else "unknown"
    return rec


def fill_missing_sizes(records: list[Record]) -> None:
    for r in records:
        p = Path(r.full_path)
        if not r.size_text:
            try:
                size_bytes = dir_size_bytes(p) if r.is_dir else p.stat().st_size
            except OSError:
                size_bytes = 0
            r.size_bytes = int(size_bytes)
            r.size_text = human_size(r.size_bytes)
        if int(r.page_count or 0) <= 0:
            if bool(r.is_dir):
                r.page_count = parse_ehviewer_page_count(ehviewer_sidecar(p, True))
            elif str(r.extension or "").lower() == ".zip":
                r.page_count = parse_ehviewer_page_count_from_zip(p)
            else:
                r.page_count = parse_ehviewer_page_count(ehviewer_sidecar(p, False))
        if not r.page_count_text:
            r.page_count_text = str(int(r.page_count or 0)) if int(r.page_count or 0) > 0 else ""
