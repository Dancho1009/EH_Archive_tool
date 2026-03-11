from __future__ import annotations

import time
from pathlib import Path
from typing import Iterable

from .parsing_record import parse_record


def iter_all_paths(roots: list[Path], recursive: bool) -> Iterable[Path]:
    for root in roots:
        if not root.exists():
            print(f"[WARN] root not found: {root}")
            continue
        it = root.rglob("*") if recursive else root.iterdir()
        for p in sorted(it):
            if p.name.startswith("."):
                continue
            if "_archive_output" in str(p):
                continue
            if recursive or p.is_file() or p.is_dir():
                yield p


def parse_with_progress(paths: list[Path]):
    total = len(paths)
    if total == 0:
        return []
    out = []
    start = time.time()
    for i, p in enumerate(paths, 1):
        out.append(parse_record(p, f"R{i:06d}"))
        if i == 1 or i == total or i % 100 == 0:
            ratio = i / total
            bar = "#" * int(30 * ratio) + "-" * (30 - int(30 * ratio))
            print(f"\r[Parse] [{bar}] {i}/{total} ({ratio*100:5.1f}%) elapsed={time.time()-start:6.1f}s", end="", flush=True)
    print()
    return out


def signature(path: Path) -> str:
    st = path.stat()
    return f"{int(path.is_dir())}|{st.st_size if path.is_file() else 0}|{st.st_mtime_ns}"
