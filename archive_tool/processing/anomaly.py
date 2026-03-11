from __future__ import annotations

import json
from pathlib import Path

from ..models import Record

RISK_DETAIL_MAP = {
    "未识别作者": "未从标题中识别出作者/社团，且该条目不是杂志。归档到作者名下可能不准确，建议人工确认。",
    "体积异常": "文件或目录体积为 0（或读取失败）。可能是损坏文件、空目录或权限问题。",
    "页数缺失": "未读取到页数信息（.ehviewer 缺失或格式异常）。可能影响主本选择与系列判断。",
    "核心标题缺失": "标题清洗后为空，说明命名格式异常或解析失败，后续去重准确度会下降。",
    "标题过长可能解析失败": "标题长度异常偏大，正则提取更容易误判，建议人工复核标题结构。",
    "跨作者严格重复关系": "当前记录被严格重复链路指向了不同作者主本，疑似误判或作者别名未归并。",
}


def _master_id(rec: Record) -> str:
    if rec.duplicate_master_id:
        return str(rec.duplicate_master_id).strip()
    if rec.duplicate_with:
        return str(rec.duplicate_with).split("|", 1)[0].strip()
    return ""


def detect_anomalies(records: list[Record], output_dir: Path) -> dict[str, int]:
    by_id = {r.record_id: r for r in records}
    rows: list[dict] = []
    high = 0
    for r in records:
        issues: list[str] = []
        if not str(r.archive_author or "").strip() and str(r.work_type or "") != "magazine":
            issues.append("未识别作者")
        if int(r.size_bytes or 0) <= 0:
            issues.append("体积异常")
        if (bool(r.is_dir) or str(r.extension or "").lower() == ".zip") and int(r.page_count or 0) <= 0:
            issues.append("页数缺失")
        if not str(r.core_title or "").strip():
            issues.append("核心标题缺失")
        if len(str(r.raw_name or "")) > 180:
            issues.append("标题过长可能解析失败")

        if r.duplicate_status == "严格重复":
            mid = _master_id(r)
            if mid and mid in by_id:
                m = by_id[mid]
                if str(r.display_author or "").strip() and str(m.display_author or "").strip() and r.display_author != m.display_author:
                    issues.append("跨作者严格重复关系")

        if issues:
            high += 1
            r.risk_level = "high"
            r.risk_flags = " | ".join(issues)
            r.risk_detail = " | ".join([f"{x}：{RISK_DETAIL_MAP.get(x, '需要人工复核此风险项。')}" for x in issues])
            rows.append(
                {
                    "record_id": r.record_id,
                    "display_author": r.display_author,
                    "raw_name": r.raw_name,
                    "full_path": r.full_path,
                    "duplicate_status": r.duplicate_status,
                    "risk_level": r.risk_level,
                    "risk_flags": r.risk_flags,
                    "risk_detail": r.risk_detail,
                }
            )
        else:
            r.risk_level = ""
            r.risk_flags = ""
            r.risk_detail = ""

    out = output_dir / "高风险待审.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Anomaly] high_risk={high}, file={out}")
    return {"high_risk_records": high}
