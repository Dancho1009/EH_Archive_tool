# 作品归档与查重工具（EhViewer命名场景支持友好）

一个面向本地同人作品库的归档工具，支持：
- 按作者（找不到作者则按社团）归档
- 同作者内查重（严格重复 / 疑似重复 / 系列相关非重复）
- 系列缺失检测（本地规则 + 可选 DeepSeek 复核）
- 导出 Excel / HTML 审核页 / JSON / 统计 JSON
- GUI 一键运行、内嵌审核、删除后同步状态并快速重导出

---

## 1. 功能概览

- 归档主线
  - 作者优先：优先提取作者名；无作者时回落到社团名
  - 作者排序后写出：每个作者下按作品名排序
- 查重
  - 严格重复：高置信重复
  - 疑似重复：需人工确认
  - 系列相关非重复：同系列不同话数/卷，不直接判重
  - GID 强规则：同 `prefix_id(gid)` 直接判为严格重复
- 元数据增强
  - 记录作品体积（`size_bytes`, `size_text`）
  - 记录页数（`page_count`, `page_count_text`）
  - `.zip` 会读取压缩包内 `.ehviewer`
  - `.ehviewer` 首行不是 `VERSION...` 视为无效并跳过
- 审核页（HTML）
  - 分页、作者筛选、作者搜索、跳转定位
  - 批量勾选、打开路径、复制、导出路径、删除
  - 拖拽刷选：按住复选框拖动，纵向扫过行即可自动勾选
- GUI
  - 参数保存与恢复（含主窗口位置/大小）
  - 内嵌审核页窗口位置/大小记忆
  - 运行日志、阶段进度、统计概览、最近运行历史

---

## 2. 项目结构

- `archive_works.py`：CLI 入口（调用 `archive_tool.cli`）
- `archive_gui.py`：PyQt 图形界面
- `archive_tool/`：核心逻辑
  - `parsing.py`：命名解析、体积/页数提取
  - `dedupe.py`：本地去重、系列规则
  - `deepseek.py`：DeepSeek 归并与语义复判
  - `pipeline.py`：主流程编排
  - `exporters.py`：Excel/HTML/JSON 导出
  - `state.py`：状态文件读写（增量依赖）
  - `review_actions.py` / `review_server.py`：审核页删除与桥接
- `result/`：默认输出目录（可改）

---

## 3. 环境要求

- Python 3.10+
- Windows（已适配 `os.startfile` 等行为）
- 依赖：
  - `openpyxl`
  - `PyQt5`
  - `PyQtWebEngine`（内嵌审核页需要）

安装示例：

```bash
pip install openpyxl PyQt5 PyQtWebEngine
```

---

## 4. 快速开始（CLI）

全量重建：

```bash
python archive_works.py ROOT1 ROOT2 --output-dir result --full-rebuild
```

增量更新：

```bash
python archive_works.py ROOT1 ROOT2 --output-dir result --incremental --state-file "result\archive_state.json"
```

启用 DeepSeek：

```bash
set DEEPSEEK_API_KEY=你的key
python archive_works.py ROOT1 ROOT2 --output-dir result --full-rebuild --use-deepseek --deepseek-model deepseek-chat --deepseek-author-merge --deepseek-candidate-mode balanced
```

查看全部参数：

```bash
python archive_works.py -h
```

---

## 5. GUI 使用

启动：

```bash
python archive_gui.py
```
或双击```start.bat```启动


建议流程：

- 首次整理：勾选“全量重建”
- 日常维护：勾选“增量”
- 若存量已人工确认：可勾“冻结存量”
- 需要语义能力时：勾“启用 DeepSeek”
- 作者别名多时：勾“作者归并”

说明：

- GUI 配置默认在 `result/gui_config.json`
- 输出默认在 `result/`
- 内嵌审核页支持直接删除，删除后会：
  - 删除本地文件/文件夹
  - 同步更新状态
  - 触发快速重导出

---

## 6. 输出文件说明

默认输出到 `result/`：

- `作品归档结果.xlsx`
- `作品归档审核页.html`（及分页目录）
- `作品归档结果.json`
- `作品归档统计.json`
- `archive_state.json`（增量状态）
- `author_merge_cache.json`（作者归并缓存）
- `运行历史.csv`
- `gui_config.json`(GUI 配置)

历史快照：
- `_history/YYYYmmdd_HHMMSS/`（保留份数可配置）

---

## 7. DeepSeek 相关

- 主要能力
  - 作者归并（别名合并）
  - 候选重复语义复判
  - 系列缺失复核
- 常用参数（可在 GUI 配置）
  - 模型：`--deepseek-model`
  - 超时：`--deepseek-timeout`
  - 重试：`--deepseek-retries`
  - 候选模式：`--deepseek-candidate-mode`
  - 作者归并批大小：`--deepseek-author-merge-batch-size`
  - 作者归并最大名称数：`--deepseek-author-merge-max-names`

---

## 8. 归并策略文件（可选）

支持通过 `merge_policy.json` 手工控制：

- 作者白名单映射
- 黑名单
- 社团到作者映射
- 歧义社团
- 冻结作者

CLI 参数：

- `--merge-policy-file <path>`
- 留空时默认读取：`<output-dir>/merge_policy.json`

---

## 9. 已实现的关键规则（如果您的文件来自ehviewer下载）

- `.zip` 的页数读取来自压缩包内 `.ehviewer`
- `.ehviewer` 第一行必须以 `VERSION` 开头，否则跳过该元数据
- 体积与页数都可导出到 Excel/HTML/JSON
- 同 GID（文件名前缀数字）可直接判重

---

## 10. 常见问题

- Q: 这个工具支持EhViewer以外的下载来源吗？  
  A: 理论上档案是按照一定规则命名的话，应该都是可以的，只是我自己常用EhViewer，故按照EhViewer的规则做的本工具。

- Q: Excel 保存失败（Permission denied）  
  A: 先关闭已打开的 Excel 再重跑；工具会尝试另存带时间戳文件。

- Q: 增量跑得很快但没有变化？  
  A: 可能 `parse_new_or_changed=0`，表示没有新增/变更文件。

- Q: 内嵌审核页打不开？  
  A: 安装 `PyQtWebEngine`；否则会回退到浏览器模式。

- Q: 为什么有些作品页数为空？  
  A: 可能没有 `.ehviewer`，或首行不是 `VERSION`(说明.ehviewer文件内容有损)，按无效元数据跳过。

- Q: 为什么本工具不在检测完后自动删除重复档案？
  A: 本工具查重正确率并非百分百正确，比起省一点人工审核去重的功夫，档案的价值无疑是更高的。

---


