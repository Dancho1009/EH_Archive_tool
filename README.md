# EHViewer下载档案归档与查重工具（EH Archive Tool）

用于Ehviewer下载的本地同人作品库的**分类归档 + 去重审查 + 系列缺失检测**。  （其他下载源本项目不保证可用性，最好是以Ehviewer下载命名的格式）

支持多目录合并扫描（zip 库 + 文件夹库），并输出 Excel、HTML 审核页、JSON 结果。

## 核心能力
- 按“作者优先，找不到作者再按社团”分组归档。
- 同作者桶内做严格重复/疑似重复/系列相关非重复判定。
- 支持 GID（文件名前缀数字）强判重复。
- 支持合集覆盖识别（如 `01-15` 覆盖 `#01..#15`）。
- 支持系列缺失检测（本地规则 + DeepSeek 复核）。
- 支持 DeepSeek 增强：作者归并、系列提取、重复簇复判、社团作者建议。
- 风险说明与 DeepSeek 复判说明（含风险标签/风险说明）。
- GUI 内置运行、日志、结果入口、审核页联动删除（删除后自动同步状态并快速重导出）。

## 项目结构
- `archive_works.py`：CLI 入口
- `archive_gui.py`：PyQt GUI 入口
- `archive_tool/processing/`：扫描、解析、去重规则
- `archive_tool/deepseek/`：DeepSeek 客户端与各阶段工作流
- `archive_tool/exporting/`：Excel/HTML/JSON 导出
- `archive_tool/workflow/`：主流程编排、运行历史、反馈学习
- `archive_tool/gui/`：GUI 主窗体与交互
- `result/`：默认输出目录

## 运行环境
- Python 3.10+
- Windows (其他平台未测试不保证可用)
- 依赖：
  - `openpyxl`
  - `PyQt5`
  - `PyQtWebEngine`

安装：

```bash
pip install openpyxl PyQt5 PyQtWebEngine
```

## 快速开始

全量重建（首次建议）：

```bash
python archive_works.py SOURCE_ROOT1 SOURCE_ROOT2 SOURCE_* --output-dir RESULT_ROOT --full-rebuild
```

增量更新：

```bash
python archive_works.py SOURCE_ROOT1 SOURCE_ROOT2 SOURCE_* --output-dir result --incremental --state-file result\archive_state.json
```

启用 DeepSeek（示例）：

```bash
set DEEPSEEK_API_KEY=你的key
python archive_works.py SOURCE_ROOT1 SOURCE_ROOT2 SOURCE_* --output-dir RESULT_ROOT --full-rebuild --use-deepseek --deepseek-model deepseek-chat --deepseek-author-merge --deepseek-candidate-mode balanced
```

DeepSeek 候选上限参数支持 `-1` 自动（推荐）：
- `--deepseek-max-candidates`
- `--deepseek-author-merge-max-names`
- `--deepseek-series-extract-max-candidates`
- `--deepseek-series-max-groups`
- `--deepseek-cluster-max-groups`
- `--deepseek-circle-author-max-circles`

查看参数说明：

```bash
python archive_works.py -h
```

GUI 启动：

```bash
python archive_gui.py
```

## 输出文件
默认输出到 `result/`：
- `作品归档结果.xlsx`
- `作品归档审核页.html`
- `作品归档结果.json`
- `作品归档统计.json`
- `archive_state.json`
- `author_merge_cache.json`
- `运行历史.csv`
- `操作日志.csv` / `操作日志.jsonl`（审核页删除操作日志）
- `审核反馈.jsonl`（删除反馈学习样本）

说明：
- `merge_policy_templete.json` 为策略填写参考模板；实际生效文件默认是 `输出目录/merge_policy.json`（或 `--merge-policy-file` 指定路径）。

## 数据与隐私
- 不上传网络时，全部处理在本地完成。
- 启用 DeepSeek 后，仅发送候选文本信息用于语义判断。
- api key以明文的方式与其他参数配置一起，保存在config.json中，请注意隐私保护。

## 详细文档
请阅读：
- [作品归档与查重说明文档.md](./作品归档与查重说明文档.md)
