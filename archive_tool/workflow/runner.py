from __future__ import annotations

import os
from pathlib import Path

from ..deepseek.workflow import (
    run_author_merge,
    run_circle_author_suggest,
    run_cluster_refine,
    run_dedupe_refine,
    run_series_extract_refine,
    run_series_missing_refine,
)
from ..exporting.pipeline import apply_exports
from ..policy import load_policy
from ..processing.dedupe import (
    dedupe_records,
    finalize_sort_keys,
    mark_compilation_coverage,
    mark_gid_duplicates,
    mark_series_missing,
    mark_suggested_authors,
    normalize_author_alias_by_gid,
    normalize_duplicate_reason_language,
    normalize_strict_duplicates,
)
from ..processing.anomaly import detect_anomalies
from ..processing.parsing import fill_missing_sizes, iter_all_paths, parse_with_progress, signature
from ..state import load_state, reset_runtime, restore_record, save_state
from .feedback import apply_feedback_learning
from .history import append_run_history
from .policy_apply import apply_manual_author_policy, resolve_policy_path


def run(args) -> None:
    """Execute full pipeline."""
    roots = [Path(x).resolve() for x in args.roots]
    all_paths = list(iter_all_paths(roots, args.recursive))
    print(f"[扫描] roots={len(roots)}, entries={len(all_paths)}, recursive={args.recursive}")
    sigs = {str(p.resolve()): signature(p) for p in all_paths}
    output_dir = Path(args.output_dir).resolve()
    policy_path = resolve_policy_path(args, output_dir)
    policy = load_policy(policy_path)
    frozen_authors = set(policy.get("freeze_authors", set()) or set())
    print(
        f"[策略] loaded={1 if policy.get('_loaded') else 0}, file={policy_path}, "
        f"whitelist={len(policy.get('author_whitelist', {}))}, "
        f"blacklist={len(policy.get('author_blacklist', set()))}, "
        f"circle_to_author={len(policy.get('circle_to_author', {}))}, "
        f"ambiguous_circles={len(policy.get('ambiguous_circles', set()))}, "
        f"freeze_authors={len(frozen_authors)}"
    )

    records = []
    parse_paths = all_paths
    parse_new_or_changed = len(all_paths)
    if args.incremental and not args.full_rebuild:
        state = load_state(Path(args.state_file).resolve())
        prev_entries = state.get("entries", {})
        prev_records = state.get("records_by_path", {})
        reused = [p for p in all_paths if prev_entries.get(str(p.resolve())) == sigs.get(str(p.resolve())) and str(p.resolve()) in prev_records]
        reused_set = {str(p.resolve()) for p in reused}
        parse_paths = [p for p in all_paths if str(p.resolve()) not in reused_set]
        parse_new_or_changed = len(parse_paths)
        for p in reused:
            rec = restore_record(prev_records[str(p.resolve())])
            rec.ingest_status = "existing"
            records.append(rec)
        print(f"[增量] reused={len(reused)}, parse_new_or_changed={len(parse_paths)}, removed={max(0, len(prev_entries)-len(sigs))}")

    parsed_records = parse_with_progress(parse_paths)
    for r in parsed_records:
        r.ingest_status = "new"
    records.extend(parsed_records)
    freeze_existing = bool(getattr(args, "freeze_existing", False) and args.incremental and not args.full_rebuild)
    reset_runtime(records, preserve_existing=freeze_existing)
    fill_missing_sizes(records)
    policy_apply_stats = apply_manual_author_policy(
        records,
        policy,
        only_new=freeze_existing,
        frozen_authors=frozen_authors,
    )
    print(
        f"[策略] 应用 scope={'new' if freeze_existing else 'all'} "
        f"whitelist_hits={policy_apply_stats['whitelist_hits']} "
        f"circle_map_hits={policy_apply_stats['circle_map_hits']} "
        f"updated_records={policy_apply_stats['updated_records']}"
    )
    input_unique_names = len({(r.author_std or r.circle_std) for r in records if (r.author_std or r.circle_std)})
    author_merge_stats = {
        "cache_hit": 0,
        "mapped": 0,
        "updated_records": 0,
    }

    if args.use_deepseek and args.deepseek_author_merge:
        if args.incremental and not args.full_rebuild and parse_new_or_changed == 0:
            print("[作者归并][跳过] 增量模式下 parse_new_or_changed=0（无新增/变更）")
        else:
            key = os.environ.get(args.deepseek_key_env, "").strip()
            if key:
                cache_file = (output_dir / "author_merge_cache.json").resolve()
                author_merge_stats = run_author_merge(
                    records,
                    args,
                    key,
                    policy=policy,
                    only_new=freeze_existing,
                    frozen_authors=frozen_authors,
                    cache_file=cache_file,
                )
                input_unique_names = int(author_merge_stats.get("input_unique_names", input_unique_names) or input_unique_names)
            else:
                print(f"[作者归并][跳过] 缺少环境变量: {args.deepseek_key_env}")

    if args.use_deepseek and getattr(args, "deepseek_circle_author_suggest", False):
        key = os.environ.get(args.deepseek_key_env, "").strip()
        if key:
            run_circle_author_suggest(records, args, key, output_dir=output_dir)
        else:
            print(f"[CircleAuthor][跳过] 缺少环境变量: {args.deepseek_key_env}")

    mark_suggested_authors(records, freeze_existing=freeze_existing, frozen_authors=frozen_authors)

    if args.use_deepseek and getattr(args, "deepseek_series_extract", False):
        key = os.environ.get(args.deepseek_key_env, "").strip()
        if key:
            run_series_extract_refine(records, args, key, new_only=freeze_existing, frozen_authors=frozen_authors)
        else:
            print(f"[系列提取][DeepSeek][跳过] 缺少环境变量: {args.deepseek_key_env}")

    mark_gid_duplicates(records, freeze_existing=freeze_existing, frozen_authors=frozen_authors)
    normalize_author_alias_by_gid(records, freeze_existing=freeze_existing, frozen_authors=frozen_authors)
    dedupe_records(records, freeze_existing=freeze_existing, frozen_authors=frozen_authors)
    mark_compilation_coverage(records, freeze_existing=freeze_existing, frozen_authors=frozen_authors)

    if args.use_deepseek:
        key = os.environ.get(args.deepseek_key_env, "").strip()
        if key:
            run_dedupe_refine(records, args, key, new_only=freeze_existing, frozen_authors=frozen_authors)
            run_cluster_refine(records, args, key, new_only=freeze_existing, frozen_authors=frozen_authors)
        else:
            print(f"[语义复判][跳过] 缺少环境变量: {args.deepseek_key_env}")

    normalize_strict_duplicates(records, freeze_existing=freeze_existing, frozen_authors=frozen_authors)

    mark_series_missing(records, freeze_existing=freeze_existing, frozen_authors=frozen_authors)

    if args.use_deepseek and args.deepseek_series_missing:
        key = os.environ.get(args.deepseek_key_env, "").strip()
        if key:
            run_series_missing_refine(records, args, key, new_only=freeze_existing, frozen_authors=frozen_authors)
        else:
            print(f"[系列缺失][DeepSeek][跳过] 缺少环境变量: {args.deepseek_key_env}")

    normalize_duplicate_reason_language(records)
    apply_feedback_learning(records, output_dir)
    detect_anomalies(records, output_dir)

    finalize_sort_keys(records)
    apply_exports(records, output_dir, history_keep=max(0, int(getattr(args, "history_keep", 3))))
    author_buckets = len({(r.display_author or "待归档确认") for r in records})
    append_run_history(
        output_dir,
        input_unique_names=input_unique_names,
        cache_hit=int(author_merge_stats.get("cache_hit", 0) or 0),
        mapped=int(author_merge_stats.get("mapped", 0) or 0),
        updated_records=int(author_merge_stats.get("updated_records", 0) or 0),
        author_buckets=author_buckets,
        parse_new_or_changed=parse_new_or_changed,
    )
    print(f"[运行历史] saved: {output_dir / '运行历史.csv'}")
    save_state(Path(args.state_file).resolve(), sigs, records)
    print(f"[状态] saved: {Path(args.state_file).resolve()}")
