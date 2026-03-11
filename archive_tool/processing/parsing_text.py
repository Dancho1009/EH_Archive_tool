from __future__ import annotations

import re

PREFIX_ID_RE = re.compile(r"^(?P<prefix>\d+)-\s*")
LEADING_PAREN_RE = re.compile(r"^\((?P<content>[^()]*)\)\s*")
FRONT_BLOCK_RE = re.compile(r"^(?:\[(?P<sq>[^\]]+)\]|【(?P<cn>[^】]+)】)\s*")
TRAILING_TAG_RE = re.compile(r"\s*(?:\[(?P<sq>[^\]]+)\]|【(?P<cn>[^】]+)】)\s*$")
PAREN_RE = re.compile(r"\((?P<content>[^()]*)\)")
YEAR_RE = re.compile(r"(19|20)\d{2}")
CHAPTER_RE = re.compile(r"(?:第\s*)?(?P<num>\d+)\s*(?:话|話)")
RANGE_RE = re.compile(r"(?P<start>\d+)\s*[-~～]\s*(?P<end>\d+)")
VOLUME_RE = re.compile(r"(?:vol\.?\s*|[#＃]\s*|\s)(?P<num>\d+(?:\.\d+)?)\s*$", re.IGNORECASE)
SERIES_EXPLICIT_RE = re.compile(
    r"^(?P<title>.+?)\s*(?:vol\.?\s*|no\.?\s*|[#＃]\s*)(?P<num>\d+(?:\.\d+)?)\s*(?P<tail>.*)$",
    re.IGNORECASE,
)
SERIES_SPACE_RE = re.compile(r"^(?P<title>.+?)\s+(?P<num>\d+(?:\.\d+)?)\s*(?P<tail>.*)$", re.IGNORECASE)
SERIES_ATTACHED_RE = re.compile(r"^(?P<title>.+?\D)(?P<num>\d+(?:\.\d+)?)(?P<tail>\s+.*)?$", re.IGNORECASE)
SERIES_SUFFIX_PATTERNS = [
    re.compile(r"(?:[#＃]\s*\d{1,4}(?:\s*[-~～]\s*\d{1,4})?)\s*$", re.IGNORECASE),
    re.compile(r"(?:第\s*\d{1,4}\s*(?:話|话|章|巻|卷))\s*$", re.IGNORECASE),
    re.compile(r"(?:vol\.?\s*\d+(?:\.\d+)?)\s*$", re.IGNORECASE),
    re.compile(r"(?:no\.?\s*\d{1,4})\s*$", re.IGNORECASE),
    re.compile(r"(?:\d{1,3}(?:\.\d+)?)\s*(?:前編|前篇|中編|中篇|後編|後篇|短編.*|番外.*)?\s*$", re.IGNORECASE),
]

LANGUAGE_KW = ("中国翻訳", "中国翻译", "中国語", "Chinese", "中文")
VERSION_KW = ("DL版", "Digital", "無修正", "无修正", "Decensored", "Uncensored")
GROUP_KW = (
    "汉化",
    "漫畫",
    "翻译",
    "翻譯",
    "scan",
    "scanlation",
    "translation",
    "个人汉化",
    "個人漫畫",
)
STATUS_KW = ("进行中", "完成版", "完全版", "ongoing")


def normalize_text(text: str) -> str:
    trans = str.maketrans({"【": "[", "】": "]", "（": "(", "）": ")", "　": " ", "～": "~", "－": "-", "—": "-"})
    return re.sub(r"\s+", " ", text.translate(trans)).strip()


def normalize_key(text: str) -> str:
    text = normalize_text(text).lower()
    text = re.sub(r"\[[^\]]+\]", "", text)
    text = re.sub(r"\([^)]+\)", "", text)
    return re.sub(r"[^0-9a-zA-Z\u3040-\u30ff\u3400-\u9fff]+", "", text)


def normalize_series_key(text: str) -> str:
    """Normalize a series-level key by stripping obvious episode suffix markers."""
    out = normalize_text(text)
    if not out:
        return ""
    changed = True
    while changed and out:
        changed = False
        for pattern in SERIES_SUFFIX_PATTERNS:
            m = pattern.search(out)
            if m:
                out = normalize_text(out[: m.start()])
                changed = True
    return normalize_key(out)


def _valid_series_num(num_text: str, explicit: bool) -> bool:
    text = str(num_text or "").strip()
    if not text:
        return False
    if "." in text:
        try:
            head = float(text)
        except ValueError:
            return False
        return 0 < head <= 300
    if not text.isdigit():
        return False
    n = int(text)
    if n <= 0:
        return False
    if n >= 1000 and not explicit:
        return False
    return n <= 300 or explicit


def _ascii_short_token(text: str) -> bool:
    t = str(text or "").strip()
    if not t:
        return True
    if any(ord(ch) > 127 for ch in t):
        return False
    if " " in t:
        return False
    return len(t) <= 4


def extract_series_suffix(name: str) -> tuple[str, str]:
    """
    Extract trailing/attached series index:
    - "催眠カノジョ2" -> ("催眠カノジョ", "2")
    - "催眠カノジョ 2.5" -> ("催眠カノジョ", "2.5")
    - "催眠カノジョ4.5 短編..." -> ("催眠カノジョ", "4.5")
    Returns (series_title, index_no). If not matched, index_no is empty.
    """
    text = normalize_text(name)
    if not text:
        return "", ""

    patterns = [
        (SERIES_EXPLICIT_RE, True),
        (SERIES_SPACE_RE, False),
        (SERIES_ATTACHED_RE, False),
    ]
    for pattern, explicit in patterns:
        m = pattern.match(text)
        if not m:
            continue
        title = normalize_text(m.group("title") or "")
        num = normalize_text(m.group("num") or "")
        if not title or not num:
            continue
        if not _valid_series_num(num, explicit):
            continue
        if not explicit and _ascii_short_token(title):
            continue
        return title, num
    return text, ""


def classify_tag(tag: str) -> str:
    t = tag.lower()
    if any(k.lower() in t for k in LANGUAGE_KW):
        return "language"
    if any(k.lower() in t for k in VERSION_KW):
        return "version"
    if any(k.lower() in t for k in STATUS_KW):
        return "status"
    if any(k.lower() in t for k in GROUP_KW):
        return "group"
    return "extra"


def is_group_like(block: str) -> bool:
    kind = classify_tag(block)
    if kind in {"group", "status"}:
        return True
    if re.search(r"(汉化|漫畫|翻译|翻譯)", block):
        return True
    return False
