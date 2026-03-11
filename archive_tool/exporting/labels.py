from __future__ import annotations

STRICT = "严格重复"
SUSPECT = "疑似重复"
SERIES_NON_DUP = "系列相关非重复"
NON_DUP = "不重复"
PENDING = "待归档确认"

STAT_LABELS = {
    "total_records": "作品总数",
    "author_buckets": "作者分组数",
    "known_authors": "识别作者数",
    "pending_author_records": "待归档确认数",
    "magazine_bucket_records": "杂志分组条目数",
    "strict_duplicates": "严格重复数",
    "suspected_duplicates": "疑似重复数",
    "series_related_non_duplicates": "系列相关非重复数",
    "series_missing_records": "系列缺失命中条目数",
    "series_missing_groups": "系列缺失系列数",
    "non_duplicates": "不重复数",
    "manual_review_items": "需人工复核数",
    "high_risk_records": "高风险待审数",
}

AUTHOR_STAT_LABELS = {
    "author": "作者",
    "works": "作品数",
    "strict_duplicates": "严格重复",
    "suspected_duplicates": "疑似重复",
    "series_related_non_duplicates": "系列相关非重复",
    "series_missing_items": "系列缺失命中",
    "non_duplicates": "不重复",
    "manual_review_items": "需人工复核",
    "high_risk_items": "高风险待审",
}

RECORD_HEADER_LABELS = {
    "record_id": "记录ID",
    "raw_name": "原始名称",
    "full_path": "完整路径",
    "parent_path": "所在目录",
    "is_dir": "是否文件夹",
    "extension": "扩展名",
    "prefix_id": "前缀编号",
    "author_raw": "原始作者",
    "circle_raw": "原始社团",
    "author_std": "标准作者",
    "circle_std": "标准社团",
    "archive_author": "归档作者",
    "display_author": "显示作者",
    "title_raw": "标题原文",
    "core_title": "核心标题",
    "dedupe_title": "去重标题",
    "chapter_no": "章节号",
    "range_start": "范围起始",
    "range_end": "范围结束",
    "volume_no": "卷号",
    "source_info": "来源信息",
    "ip_info": "IP信息",
    "size_bytes": "大小(字节)",
    "size_text": "大小",
    "page_count": "页数",
    "page_count_text": "页数字段",
    "language_tags": "语言标签",
    "version_tags": "版本标签",
    "group_tag": "分组标签",
    "status_tags": "状态标记",
    "work_type": "作品类型",
    "author_affinity_status": "作者归并状态",
    "suggested_author": "建议作者",
    "suggested_author_reason": "建议原因",
    "suggested_author_confidence": "建议置信度",
    "duplicate_status": "重复状态",
    "duplicate_group_id": "重复组ID",
    "duplicate_master_id": "主记录ID",
    "duplicate_with": "重复来源",
    "duplicate_source_path": "重复来源路径",
    "duplicate_reason": "重复原因",
    "duplicate_confidence": "重复置信度",
    "series_key": "系列键",
    "series_index_type": "序号类型",
    "series_indices": "已收录序号",
    "series_missing": "系列缺失",
    "series_missing_numbers": "缺失序号",
    "series_missing_reason": "缺失原因",
    "series_missing_confidence": "缺失置信度",
    "manual_review": "人工复核",
    "author_sort_key": "作者排序键",
    "title_sort_key": "标题排序键",
    "risk_level": "风险等级",
    "risk_flags": "风险标签",
    "risk_detail": "风险说明",
    "notes": "备注",
}

REVIEW_MAIN_HTML = "作品归档审核页.html"
REVIEW_PAGE_DIR = "作品归档审核页_pages"
