from __future__ import annotations

import os
import re
import zipfile
from pathlib import Path


def human_size(size_bytes: int) -> str:
    if size_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    val = float(size_bytes)
    idx = 0
    while val >= 1024.0 and idx < len(units) - 1:
        val /= 1024.0
        idx += 1
    if idx == 0:
        return f"{int(val)} {units[idx]}"
    return f"{val:.2f} {units[idx]}"


def dir_size_bytes(root: Path) -> int:
    total = 0
    stack = [root]
    while stack:
        cur = stack.pop()
        try:
            with os.scandir(cur) as it:
                for ent in it:
                    try:
                        if ent.is_symlink():
                            continue
                        if ent.is_file(follow_symlinks=False):
                            total += ent.stat(follow_symlinks=False).st_size
                        elif ent.is_dir(follow_symlinks=False):
                            stack.append(Path(ent.path))
                    except OSError:
                        continue
        except OSError:
            continue
    return total


def ehviewer_sidecar(path: Path, is_dir: bool) -> Path | None:
    if is_dir:
        p = path / ".ehviewer"
        return p if p.exists() and p.is_file() else None
    p = path.parent / f"{path.stem}.ehviewer"
    if p.exists() and p.is_file():
        return p
    return None


def parse_ehviewer_page_count_from_lines(lines: list[str]) -> int:
    if not lines:
        return 0
    if not str(lines[0] or "").strip().upper().startswith("VERSION"):
        return 0

    if len(lines) >= 8 and lines[7].strip().isdigit():
        try:
            val = int(lines[7].strip())
            if val > 0:
                return val
        except ValueError:
            pass

    if len(lines) >= 2:
        try:
            idx_hex = int(lines[1].strip(), 16)
            if idx_hex >= 0:
                return idx_hex + 1
        except ValueError:
            pass

    max_idx = -1
    for s in lines:
        m = re.match(r"^\s*(\d+)\s+", s)
        if m:
            max_idx = max(max_idx, int(m.group(1)))
    return max_idx + 1 if max_idx >= 0 else 0


def parse_ehviewer_page_count(meta_path: Path | None) -> int:
    if not meta_path:
        return 0
    try:
        lines = meta_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return 0
    return parse_ehviewer_page_count_from_lines(lines)


def parse_ehviewer_page_count_from_zip(zip_path: Path) -> int:
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            candidates = [n for n in names if n == ".ehviewer" or n.endswith("/.ehviewer") or n.endswith("\\.ehviewer")]
            if not candidates:
                return 0
            target = sorted(candidates, key=len)[0]
            raw = zf.read(target)
    except (OSError, zipfile.BadZipFile, KeyError):
        return 0
    lines = raw.decode("utf-8", errors="replace").splitlines()
    return parse_ehviewer_page_count_from_lines(lines)
