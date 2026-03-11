from __future__ import annotations

import re

SCAN_RE = re.compile(r"\[(?:Scan|扫描)\].*entries=(\d+)")
PROGRESS_RE = re.compile(r"\[(Parse|解析|AuthorMerge|作者归并|DeepSeek|SeriesMissing\]\[DeepSeek)\].*?(\d+)/(\d+)")
AUTHOR_CAND_RE = re.compile(r"\[(?:AuthorMerge|作者归并)\].*(?:candidates|候选)=(\d+)")
DEEP_CAND_RE = re.compile(r"\[DeepSeek\]\s*candidates=(\d+)")
DEEP_RESULT_RE = re.compile(r"\[DeepSeek\]\s*refined=(\d+),\s*failed=(\d+),\s*candidates=(\d+)")
ERR_HINTS = ("[FAIL]", "[RETRY]", "[SKIP]", "[WARN]", "Traceback")
