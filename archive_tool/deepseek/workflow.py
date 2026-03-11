from __future__ import annotations

"""
Backward-compatible DeepSeek workflow facade.

Public API remains unchanged for callers.
Implementations live in `archive_tool.deepseek.workflow_parts`.
"""

from .workflow_parts import (
    run_author_merge,
    run_circle_author_suggest,
    run_cluster_refine,
    run_dedupe_refine,
    run_series_extract_refine,
    run_series_missing_refine,
)

__all__ = [
    "run_author_merge",
    "run_circle_author_suggest",
    "run_cluster_refine",
    "run_dedupe_refine",
    "run_series_extract_refine",
    "run_series_missing_refine",
]
