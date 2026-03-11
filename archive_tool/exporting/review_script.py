from __future__ import annotations

from pathlib import Path

_ASSET_PATH = Path(__file__).with_name("assets") / "review_page.js"
REVIEW_PAGE_SCRIPT = _ASSET_PATH.read_text(encoding="utf-8")
