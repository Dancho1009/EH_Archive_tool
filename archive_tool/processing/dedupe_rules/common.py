from __future__ import annotations

import re

from ...models import Record

ISSUE_RE_1 = re.compile(r"(?P<y>(?:19|20)\d{2})\s*[-/.]\s*(?P<m>\d{1,2})")
ISSUE_RE_2 = re.compile(r"(?P<y>(?:19|20)\d{2})\s*年\s*(?P<m>\d{1,2})\s*月")
ISSUE_RE_3 = re.compile(r"(?P<y>(?:19|20)\d{2})\s*(?:No\.?|NO\.?|no\.?|#)\s*(?P<n>\d{1,3})")
GID_FALLBACK_RE = re.compile(r"(?<!\d)(?P<gid>\d{6,8})-\s*")

_REASON_MAP = [
    (r"same core[_\s-]*title|core[_\s-]*title", "核心标题一致"),
    (r"same author|author", "作者一致"),
    (r"same gid|gid", "GID一致"),
    (r"same page[_\s-]*count|page[_\s-]*count|page count", "页数一致"),
    (r"no chapter|no volume|no .*differences", "未检测到卷/话差异"),
    (r"master.*size[_\s-]*bytes|larger size|smaller size|size[_\s-]*bytes|size bytes", "存在体积差异"),
    (r"compression|format variation|format", "可能存在压缩率或封装格式差异"),
    (r"duplicate", "判定重复"),
    (r"series", "系列相关非重复"),
    (r"missing|gap", "疑似存在缺失序号"),
    (r"cross[-\s]*author|different author", "跨作者关系"),
    (r"likely|potential|possible", "模型给出概率性判断"),
    (r"review", "需人工复核"),
    (r"not duplicate|unique", "判定不重复"),
]


def next_duplicate_group_seed(records: list[Record]) -> int:
    nums: list[int] = []
    for r in records:
        m = re.match(r"^D(\d+)$", str(r.duplicate_group_id or ""))
        if m:
            nums.append(int(m.group(1)))
    return (max(nums) + 1) if nums else 1


def normalized_gid(rec: Record) -> str:
    """Best-effort gid extraction for dedupe/alias logic."""
    gid = str(rec.prefix_id or "").strip()
    if gid:
        return gid
    text = " ".join([str(rec.raw_name or ""), str(rec.title_raw or "")]).strip()
    m = GID_FALLBACK_RE.search(text)
    if not m:
        return ""
    return m.group("gid")


def gid_master_score(rec: Record) -> tuple[int, int, int, int, str]:
    """Score for selecting one master inside same gid group."""
    vtags = str(rec.version_tags or "").lower()
    uncensored = 1 if ("无修正" in vtags or "無修正" in vtags or "uncensored" in vtags or "decensored" in vtags) else 0
    size = int(rec.size_bytes or 0)
    file_pref = 1 if not rec.is_dir else 0
    zip_pref = 1 if str(rec.extension or "").lower() == ".zip" else 0
    return (uncensored, size, file_pref, zip_pref, str(rec.raw_name or ""))


def issue_token(rec: Record) -> str:
    """Extract normalized magazine issue token YYYY-MM from raw/source text."""
    text = f"{rec.raw_name} {rec.source_info}".strip()
    m = ISSUE_RE_1.search(text) or ISSUE_RE_2.search(text)
    if not m:
        n = ISSUE_RE_3.search(text)
        if not n:
            return ""
        year = int(n.group("y"))
        no = int(n.group("n"))
        if no < 1 or no > 999:
            return ""
        return f"{year:04d}-NO{no:03d}"
    year = int(m.group("y"))
    month = int(m.group("m"))
    if month < 1 or month > 12:
        return ""
    return f"{year:04d}-{month:02d}"


def reason_to_cn(reason: str) -> str:
    text = str(reason or "").strip()
    if not text:
        return ""
    if sum(1 for ch in text if ord(ch) > 127) >= max(2, len(text) // 6):
        return text
    low = text.lower()
    parts: list[str] = []
    for patt, zh in _REASON_MAP:
        if re.search(patt, low):
            parts.append(zh)
    if not parts:
        return "模型说明：未命中可解释规则，建议人工复核"
    uniq: list[str] = []
    seen = set()
    for p in parts:
        if p in seen:
            continue
        seen.add(p)
        uniq.append(p)
    return "；".join(uniq)


def _normalize_deepseek_reason(raw: str, *, default_prefix: str, aliases: list[str]) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    if "DeepSeek" not in text and sum(1 for ch in text if ord(ch) > 127) >= max(2, len(text) // 6):
        return text

    prefix = ""
    content = text
    for alias in aliases:
        for sep in ("：", ":"):
            token = f"{alias}{sep}"
            if text.startswith(token):
                prefix = f"{alias}："
                content = text[len(token) :].strip()
                break
        if prefix:
            break

    if not prefix and text.startswith("DeepSeek:"):
        prefix = default_prefix
        content = text[len("DeepSeek:") :].strip()
    elif not prefix and text.startswith("DeepSeek"):
        # Unknown deepseek label form: normalize to default prefix.
        pos = text.find(":")
        if pos != -1 and pos < 40:
            content = text[pos + 1 :].strip()
        prefix = default_prefix

    localized = reason_to_cn(content)
    if not localized:
        localized = content
    return f"{prefix}{localized}" if prefix else localized


def normalize_duplicate_reason_language(records: list[Record]) -> int:
    """Normalize DeepSeek reason fields to Chinese for export consistency."""
    updated = 0
    for r in records:
        raw_dup = str(r.duplicate_reason or "").strip()
        new_dup = _normalize_deepseek_reason(
            raw_dup,
            default_prefix="DeepSeek语义复判：",
            aliases=["DeepSeek语义复判", "DeepSeek簇复判"],
        )
        if new_dup and new_dup != raw_dup:
            r.duplicate_reason = new_dup
            updated += 1

        raw_series = str(r.series_missing_reason or "").strip()
        new_series = _normalize_deepseek_reason(
            raw_series,
            default_prefix="DeepSeek系列缺失复核：",
            aliases=["DeepSeek系列缺失复核", "DeepSeek系列复核"],
        )
        if new_series and new_series != raw_series:
            r.series_missing_reason = new_series
            updated += 1

        raw_suggest = str(r.suggested_author_reason or "").strip()
        new_suggest = _normalize_deepseek_reason(
            raw_suggest,
            default_prefix="DeepSeek作者建议：",
            aliases=["DeepSeek作者建议", "DeepSeek社团作者建议"],
        )
        if new_suggest and new_suggest != raw_suggest:
            r.suggested_author_reason = new_suggest
            updated += 1
    if updated:
        print(f"[ReasonCN] updated={updated}")
    return updated


def series_hint(rec: Record) -> tuple[str, str, str]:
    return str(rec.chapter_no or "").strip(), str(rec.volume_no or "").strip(), issue_token(rec)


def series_mismatch_reason(a: Record, b: Record) -> str:
    """Human-readable mismatch reason with magazine-first policy."""
    a_ch, a_vol, a_issue = series_hint(a)
    b_ch, b_vol, b_issue = series_hint(b)

    if a.work_type == "magazine" or b.work_type == "magazine":
        if a_issue and b_issue and a_issue != b_issue:
            return "杂志期号不同"
        if (a_issue and not b_issue) or (b_issue and not a_issue):
            return "杂志期号信息不一致"

    if (a_issue or b_issue) and a_issue != b_issue:
        return "期号不同"
    if (a_ch or b_ch) and a_ch != b_ch:
        return "话次不同"
    if (a_vol or b_vol) and a_vol != b_vol:
        return "卷次不同"

    # Fallback: detect numeric episode markers from raw names when parser misses chapter_no.
    ai = record_index_no(a)
    bi = record_index_no(b)
    if ai is not None and bi is not None and ai != bi:
        return "系列序号不同"

    a_rng = (a.range_start, a.range_end)
    b_rng = (b.range_start, b.range_end)
    if any(x is not None for x in a_rng + b_rng) and a_rng != b_rng:
        return "章节区间不同"
    return ""


def to_int(value: str) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    if re.fullmatch(r"\d+", text):
        return int(text)
    return None


def detect_gap(numbers: set[int]) -> list[int]:
    if len(numbers) < 2:
        return []
    lo, hi = min(numbers), max(numbers)
    if lo < 0 or hi - lo > 200:
        return []
    missing = [n for n in range(lo, hi + 1) if n not in numbers]
    if len(missing) > 30:
        return []
    return missing


def series_anchor_key(rec: Record) -> str:
    """Loose series key for linking single episodes with compilation ranges."""
    text = str(rec.core_title or rec.title_raw or rec.raw_name or "").strip().lower()
    text = re.sub(r"[#＃]\s*\d{1,4}.*$", "", text)
    text = re.sub(r"第\s*\d{1,4}\s*(?:話|话).*$", "", text)
    text = re.sub(r"\d{1,3}(?:\.\d+)?\s*(?:前編|前篇|中編|中篇|後編|後篇|短編.*|番外.*)?$", "", text)
    text = text.strip(" ._:-~〜～")
    key = "".join(ch for ch in text if ch.isalnum())
    return key or rec.dedupe_title


def record_index_no(rec: Record) -> int | None:
    c = to_int(rec.chapter_no)
    if c is not None:
        return c
    m = re.search(r"[#＃]\s*(\d{1,4})", rec.raw_name or "")
    if m:
        n = int(m.group(1))
        if 0 < n <= 500:
            return n
    m = re.search(r"第\s*(\d{1,4})\s*(?:話|话)", rec.raw_name or "")
    if m:
        n = int(m.group(1))
        if 0 < n <= 500:
            return n
    return None


def is_omnibus_hint(rec: Record) -> bool:
    text = " ".join([str(rec.core_title or ""), str(rec.title_raw or ""), str(rec.raw_name or "")]).lower()
    hints = ("総集", "总集", "合集", "合辑", "合本", "完整版", "完全版", "omnibus")
    return any(h in text for h in hints)
