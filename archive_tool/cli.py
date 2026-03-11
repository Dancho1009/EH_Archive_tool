from __future__ import annotations

import argparse

from .workflow.runner import run


class _Fmt(argparse.ArgumentDefaultsHelpFormatter, argparse.RawTextHelpFormatter):
    """Readable help formatter with defaults and multiline examples."""


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser with full option help."""
    epilog = (
        "Examples:\n"
        "  Full rebuild:\n"
        "    python archive_works.py ROOT_ZIP ROOT_FOLDER --full-rebuild --use-deepseek --deepseek-author-merge\n\n"
        "  Incremental update:\n"
        "    python archive_works.py ROOT_ZIP ROOT_FOLDER --incremental --state-file result/archive_state.json\n"
    )
    p = argparse.ArgumentParser(
        description="作品归档与查重脚本",
        formatter_class=_Fmt,
        epilog=epilog,
    )
    p.add_argument("roots", nargs="*", default=["."], help="要扫描的根目录列表，可传多个（会合并去重）")
    p.add_argument("--output-dir", default="result", help="输出目录")
    p.add_argument("--history-keep", type=int, default=3, help="输出结果历史保留份数；0 表示不保留")
    p.add_argument("--recursive", action="store_true", help="递归扫描子目录")
    p.add_argument("--incremental", action="store_true", help="增量模式：复用未变化记录")
    p.add_argument("--full-rebuild", action="store_true", help="全量重建：忽略状态缓存")
    p.add_argument("--freeze-existing", action="store_true", help="增量时冻结存量记录，仅对新增/变更记录执行归并与查重更新")
    p.add_argument("--state-file", default="result/archive_state.json", help="状态文件路径")
    p.add_argument("--merge-policy-file", default="", help="归并策略文件路径（JSON）；留空默认 output-dir/merge_policy.json")

    p.add_argument("--use-deepseek", action="store_true", help="启用 DeepSeek 精判/归并")
    p.add_argument("--deepseek-model", default="deepseek-chat", help="DeepSeek 模型名")
    p.add_argument("--deepseek-base-url", default="https://api.deepseek.com", help="DeepSeek API 基础地址")
    p.add_argument("--deepseek-key-env", default="DEEPSEEK_API_KEY", help="DeepSeek API Key 环境变量名")
    p.add_argument("--deepseek-max-candidates", type=int, default=-1, help="最多提交给 DeepSeek 的去重候选数；-1 表示自动使用全部候选")
    p.add_argument("--deepseek-timeout", type=int, default=20, help="DeepSeek 单请求超时秒数")
    p.add_argument("--deepseek-retries", type=int, default=2, help="DeepSeek 单条请求重试次数")
    p.add_argument("--deepseek-retry-sleep", type=float, default=2.0, help="DeepSeek 重试基础等待秒数")
    p.add_argument("--deepseek-series-extract", action="store_true", help="用 DeepSeek 辅助提取系列标题与序号（解析后、去重前）")
    p.add_argument("--deepseek-series-extract-max-candidates", type=int, default=-1, help="DeepSeek 系列提取最多处理作品数；-1 表示自动使用全部候选")
    p.add_argument("--deepseek-series-extract-min-confidence", type=int, default=70, help="DeepSeek 系列提取回写最小置信度")
    p.add_argument("--deepseek-cluster-refine", action="store_true", help="启用 DeepSeek 重复簇复判（按簇选主本）")
    p.add_argument("--deepseek-cluster-max-groups", type=int, default=-1, help="DeepSeek 重复簇复判最多处理分组数；-1 表示自动使用全部候选分组")
    p.add_argument("--deepseek-cluster-max-size", type=int, default=12, help="DeepSeek 重复簇复判单分组最大作品数")
    p.add_argument(
        "--deepseek-candidate-mode",
        choices=["strict", "balanced", "aggressive"],
        default="strict",
        help="DeepSeek 候选范围：strict仅疑似重复，balanced疑似+系列相关，aggressive全部关联候选",
    )

    p.add_argument("--deepseek-author-merge", action="store_true", help="开启全量作者归并（先于去重）")
    p.add_argument("--deepseek-author-merge-max-names", type=int, default=-1, help="作者归并最多提交的唯一名称数；-1 表示自动使用全部候选名称")
    p.add_argument("--deepseek-author-merge-batch-size", type=int, default=30, help="作者归并每批名称数")
    p.add_argument("--deepseek-author-merge-min-confidence", type=int, default=70, help="作者归并回写最小置信度")
    p.add_argument(
        "--deepseek-author-merge-stop-after-fail-batches",
        type=int,
        default=2,
        help="作者归并连续失败批次数达到阈值后提前停止",
    )
    p.add_argument("--deepseek-series-missing", action="store_true", help="用 DeepSeek 复核系列缺失（在本地规则基础上补充）")
    p.add_argument("--deepseek-series-max-groups", type=int, default=-1, help="DeepSeek 系列缺失复核最大分组数；-1 表示自动使用候选分组数")
    p.add_argument("--deepseek-series-min-confidence", type=int, default=70, help="DeepSeek 系列缺失回写最小置信度")
    p.add_argument("--deepseek-circle-author-suggest", action="store_true", help="用 DeepSeek 生成社团->作者关系建议文件")
    p.add_argument("--deepseek-circle-author-max-circles", type=int, default=-1, help="社团->作者建议最多处理社团数；-1 表示自动使用全部候选社团")
    p.add_argument("--deepseek-circle-author-batch-size", type=int, default=25, help="社团->作者建议每批社团数")
    p.add_argument("--deepseek-circle-author-min-confidence", type=int, default=70, help="社团->作者建议最小置信度")
    return p


def main() -> None:
    """CLI entrypoint."""
    args = build_parser().parse_args()
    run(args)



