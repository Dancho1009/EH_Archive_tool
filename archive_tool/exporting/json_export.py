from __future__ import annotations

import json
from pathlib import Path


def export_json_outputs(
    rows: list[dict],
    stats: dict,
    author_stats: list[dict],
    output_dir: Path,
) -> tuple[Path, Path]:
    result_path = output_dir / "作品归档结果.json"
    stats_path = output_dir / "作品归档统计.json"
    result_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    stats_path.write_text(
        json.dumps({"overall": stats, "authors": author_stats}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result_path, stats_path
