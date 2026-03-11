from __future__ import annotations

import re

from ...models import Record

ISSUE_RE_1 = re.compile(r"(?P<y>(?:19|20)\d{2})\s*[-/.]\s*(?P<m>\d{1,2})")
ISSUE_RE_2 = re.compile(r"(?P<y>(?:19|20)\d{2})\s*年\s*(?P<m>\d{1,2})\s*月")
SERIES_NO_RE = re.compile(r"\d+")


def parse_confidence(value) -> int:
    if isinstance(value, (int, float)):
        return max(0, min(100, int(value)))
    if value is None:
        return 0
    text = str(value).strip().lower()
    label_map = {
        "high": 90,
        "medium": 70,
        "low": 40,
        "very high": 95,
        "very low": 20,
    }
    if text in label_map:
        return label_map[text]
    m = re.search(r"\d+", text)
    if m:
        return max(0, min(100, int(m.group(0))))
    return 0


def issue_token(rec: Record) -> str:
    text = f"{rec.raw_name} {rec.source_info}".strip()
    m = ISSUE_RE_1.search(text) or ISSUE_RE_2.search(text)
    if not m:
        return ""
    year = int(m.group("y"))
    month = int(m.group("m"))
    if month < 1 or month > 12:
        return ""
    return f"{year:04d}-{month:02d}"


def obvious_series_nonduplicate(a: Record, b: Record) -> bool:
    a_issue, b_issue = issue_token(a), issue_token(b)
    if (a_issue or b_issue) and a_issue != b_issue:
        return True

    a_ch, b_ch = str(a.chapter_no or "").strip(), str(b.chapter_no or "").strip()
    if (a_ch or b_ch) and a_ch != b_ch:
        return True

    a_vol, b_vol = str(a.volume_no or "").strip(), str(b.volume_no or "").strip()
    if (a_vol or b_vol) and a_vol != b_vol:
        return True

    a_rng = (a.range_start, a.range_end)
    b_rng = (b.range_start, b.range_end)
    if any(x is not None for x in a_rng + b_rng) and a_rng != b_rng:
        return True
    return False


def sequence_hint(rec: Record) -> bool:
    if rec.chapter_no or rec.volume_no or rec.range_start is not None or rec.range_end is not None:
        return True
    return bool(SERIES_NO_RE.search(rec.raw_name or ""))


def series_present_numbers(group: list[Record], index_type: str) -> list[int]:
    nums: set[int] = set()
    if index_type == "chapter":
        for r in group:
            if r.range_start is not None and r.range_end is not None and r.range_start <= r.range_end and (r.range_end - r.range_start) <= 200:
                nums.update(range(int(r.range_start), int(r.range_end) + 1))
            if str(r.chapter_no or "").strip().isdigit():
                nums.add(int(str(r.chapter_no).strip()))
    elif index_type == "volume":
        for r in group:
            if str(r.volume_no or "").strip().isdigit():
                nums.add(int(str(r.volume_no).strip()))
    return sorted(nums)


def normalize_missing_numbers(raw) -> list[int]:
    if isinstance(raw, list):
        vals = raw
    elif raw is None:
        vals = []
    else:
        vals = re.findall(r"\d+", str(raw))
    out: set[int] = set()
    for x in vals:
        try:
            n = int(x)
        except Exception:
            continue
        if 0 < n <= 500:
            out.add(n)
    return sorted(out)
