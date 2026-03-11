from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path


def save_history_snapshot(output_dir: Path, history_keep: int, files: list[Path]) -> None:
    if history_keep <= 0:
        return
    hist_root = output_dir / "_history"
    hist_root.mkdir(parents=True, exist_ok=True)
    run_dir = hist_root / datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)

    for src in files:
        if src.exists() and src.is_file():
            shutil.copy2(src, run_dir / src.name)

    runs = sorted(
        [x for x in hist_root.iterdir() if x.is_dir()],
        key=lambda x: x.stat().st_mtime,
        reverse=True,
    )
    for old in runs[history_keep:]:
        shutil.rmtree(old, ignore_errors=True)
