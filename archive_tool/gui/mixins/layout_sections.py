from __future__ import annotations

from PyQt5.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class GuiLayoutSectionsMixin:
    def _build_roots(self, parent: QVBoxLayout) -> None:
        parent.addWidget(self._create_roots_frame())

    def _create_roots_frame(self) -> QWidget:
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        v = QVBoxLayout(frame)
        title = QLabel("扫描目录（可多个）")
        title.setToolTip(
            "放入要归档的根目录（支持多个）。\n"
            "工具会把多个目录合并后统一归并和去重。\n"
            "目录顺序可调整，便于你按优先级管理来源。"
        )
        v.addWidget(title)

        self.roots_list = QListWidget()
        self.roots_list.setMinimumHeight(130)
        self.roots_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.roots_list.model().rowsMoved.connect(lambda *_: self._save_config(True))
        v.addWidget(self.roots_list)

        row = QHBoxLayout()
        for text, tip, fn in [
            ("添加目录", "添加一个新的扫描目录。", self._add_root),
            ("移除选中", "移除当前选中的目录。", self._remove_root),
            ("上移", "将选中目录上移一位。", self._up_root),
            ("下移", "将选中目录下移一位。", self._down_root),
            ("目录去重", "删除重复目录并统一路径格式。", self._dedupe_roots),
            ("清空", "清空所有扫描目录。", self._clear_roots),
        ]:
            btn = QPushButton(text)
            btn.setToolTip(tip)
            btn.clicked.connect(fn)
            row.addWidget(btn)
        row.addStretch(1)
        v.addLayout(row)
        return frame

    def _build_log(self, parent: QVBoxLayout) -> None:
        parent.addWidget(self._create_log_frame(), 1)

    def _create_log_frame(self) -> QWidget:
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        v = QVBoxLayout(frame)
        title = QLabel("运行日志")
        title.setToolTip(
            "显示主流程日志（扫描、解析、作者归并、DeepSeek 复判、导出等）。\n"
            "运行中会实时更新进度；异常会在“异常聚合”区域汇总。"
        )
        v.addWidget(title)
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumBlockCount(self.max_log_lines)
        v.addWidget(self.log_text)
        return frame

    def _build_err(self, parent: QVBoxLayout) -> None:
        parent.addWidget(self._create_err_frame())

    def _create_err_frame(self) -> QWidget:
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        v = QVBoxLayout(frame)
        row = QHBoxLayout()
        label = QLabel("异常聚合")
        label.setToolTip(
            "聚合显示去重结果中的失败、告警、网络异常、权限异常等关键问题。\n"
            "同一条异常只记录一次，避免日志刷屏。"
        )
        row.addWidget(label)
        btn_clear = QPushButton("清空异常")
        btn_clear.setToolTip("清空当前异常聚合显示，不影响实际处理结果。")
        btn_clear.clicked.connect(self._clear_errors)
        row.addWidget(btn_clear)
        row.addStretch(1)
        v.addLayout(row)
        self.error_text = QPlainTextEdit()
        self.error_text.setReadOnly(True)
        self.error_text.setMaximumBlockCount(1200)
        self.error_text.setMinimumHeight(80)
        v.addWidget(self.error_text)
        return frame

    def _build_info_tabs(self, parent: QVBoxLayout) -> None:
        tabs = QTabWidget()
        self.info_tabs = tabs
        tabs.setDocumentMode(True)
        tabs.setToolTip(
            "运行信息分为三个页签：\n"
            "1) 运行状态：当前任务实时进度\n"
            "2) 结果统计：当前输出结果指标\n"
            "3) 上次运行：最近一次运行历史快照"
        )
        tabs.addTab(self._create_runtime_frame(), "运行状态")
        tabs.addTab(self._create_stats_frame(), "结果统计")
        tabs.addTab(self._create_last_run_frame(), "上次运行")
        tabs.setCurrentIndex(2)
        parent.addWidget(tabs)

    def _build_runtime(self, parent: QVBoxLayout) -> None:
        parent.addWidget(self._create_runtime_frame())

    def _create_runtime_frame(self) -> QWidget:
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        g = QGridLayout(frame)
        self.lbl_entries = QLabel("0")
        self.lbl_parse = QLabel("0%")
        self.lbl_author = QLabel("-")
        self.lbl_deep = QLabel("-")
        self.lbl_failed = QLabel("0")
        self.lbl_elapsed = QLabel("0s")

        g.addWidget(
            self._tip_label(
                "扫描条目",
                "当前识别到的输入条目总数（zip 或文件夹）。\n"
                "这是后续解析和去重的基础规模。"
            ),
            0,
            0,
        )
        g.addWidget(self.lbl_entries, 0, 1)
        g.addWidget(
            self._tip_label(
                "解析进度",
                "解析命名、提取作者/社团、标题、页数、体积等元数据的进度。\n"
                "显示格式：百分比 + 已处理/总条目。"
            ),
            0,
            2,
        )
        g.addWidget(self.lbl_parse, 0, 3)
        g.addWidget(
            self._tip_label(
                "作者归并",
                "作者归并阶段状态。\n"
                "当启用 DeepSeek 作者归并时，这里显示候选数或进度百分比。"
            ),
            1,
            0,
        )
        g.addWidget(self.lbl_author, 1, 1)
        g.addWidget(
            self._tip_label(
                "语义复判",
                "DeepSeek 复判阶段状态。\n"
                "包括候选送审、复判完成数、失败数等。",
            ),
            1,
            2,
        )
        g.addWidget(self.lbl_deep, 1, 3)
        g.addWidget(
            self._tip_label(
                "失败/告警数",
                "运行期间捕获到的失败和告警累计数量。\n"
                "建议关注该值是否异常升高。",
            ),
            2,
            0,
        )
        g.addWidget(self.lbl_failed, 2, 1)
        g.addWidget(
            self._tip_label(
                "已用时",
                "当前任务已运行时间。\n"
                "可用于估算全量或增量所需时长。",
            ),
            2,
            2,
        )
        g.addWidget(self.lbl_elapsed, 2, 3)
        return frame

    def _build_stats(self, parent: QVBoxLayout) -> None:
        parent.addWidget(self._create_stats_frame())

    def _create_stats_frame(self) -> QWidget:
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        g = QGridLayout(frame)
        self.lbl_total = QLabel("-")
        self.lbl_buckets = QLabel("-")
        self.lbl_known = QLabel("-")
        self.lbl_strict = QLabel("-")
        self.lbl_suspect = QLabel("-")
        self.lbl_series = QLabel("-")
        self.lbl_series_missing = QLabel("-")

        g.addWidget(
            self._tip_label(
                "作品总数",
                "最终纳入本次结果的记录总数。\n"
                "它等于归档输出中的记录行数。"
            ),
            0,
            0,
        )
        g.addWidget(self.lbl_total, 0, 1)
        g.addWidget(
            self._tip_label(
                "作者分组数",
                "按“作者优先，找不到作者再按社团”归并后的分组数量。\n"
                "用于观察归并是否过散或过度合并。",
            ),
            0,
            2,
        )
        g.addWidget(self.lbl_buckets, 0, 3)
        g.addWidget(
            self._tip_label(
                "识别作者数",
                "成功识别作者或社团的记录数。\n"
                "越高表示命名解析质量越好。"
            ),
            1,
            0,
        )
        g.addWidget(self.lbl_known, 1, 1)
        g.addWidget(
            self._tip_label(
                "严格重复",
                "高置信重复条目数。\n"
                "通常可直接进入删除候选，但仍建议关键样本人工复核。"
            ),
            1,
            2,
        )
        g.addWidget(self.lbl_strict, 1, 3)
        g.addWidget(
            self._tip_label(
                "疑似重复",
                "仍需人工复核的重复候选条目数。\n"
                "建议优先在 HTML 审核页处理这一类。"
            ),
            2,
            0,
        )
        g.addWidget(self.lbl_suspect, 2, 1)
        g.addWidget(
            self._tip_label(
                "系列相关非重复",
                "同系列但不是重复的条目数（如不同卷/话、前后篇）。\n"
                "用于避免误删系列章节。",
            ),
            2,
            2,
        )
        g.addWidget(self.lbl_series, 2, 3)
        g.addWidget(
            self._tip_label(
                "系列缺失命中",
                "被识别出存在“系列缺失风险”的条目数。\n"
                "用于提示你补齐缺失卷次。"
            ),
            3,
            0,
        )
        g.addWidget(self.lbl_series_missing, 3, 1)
        return frame

    def _build_last_run(self, parent: QVBoxLayout) -> None:
        parent.addWidget(self._create_last_run_frame())

    def _create_last_run_frame(self) -> QWidget:
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        g = QGridLayout(frame)
        self.lbl_last_time = QLabel("-")
        self.lbl_last_input_names = QLabel("-")
        self.lbl_last_cache_hit = QLabel("-")
        self.lbl_last_mapped = QLabel("-")
        self.lbl_last_updated = QLabel("-")
        self.lbl_last_author_buckets = QLabel("-")
        self.lbl_last_parse_new = QLabel("-")

        g.addWidget(
            self._tip_label(
                "上一次运行历史",
                "显示最近一次任务的关键统计快照。\n"
                "可用于和当前结果做对比，判断改动是否生效。"
            ),
            0,
            0,
            1,
            4,
        )
        g.addWidget(self._tip_label("时间", "上一次任务结束时间。"), 1, 0)
        g.addWidget(self.lbl_last_time, 1, 1)
        g.addWidget(
            self._tip_label(
                "输入唯一名称数",
                "归并前，作者/社团去重后的唯一名称数量。\n"
                "用于估算作者归并工作量。"
            ),
            1,
            2,
        )
        g.addWidget(self.lbl_last_input_names, 1, 3)
        g.addWidget(
            self._tip_label(
                "归并缓存命中",
                "命中 author_merge_cache 的条目数。\n"
                "命中越高，后续运行越快。"
            ),
            2,
            0,
        )
        g.addWidget(self.lbl_last_cache_hit, 2, 1)
        g.addWidget(
            self._tip_label(
                "归并映射数",
                "本次新增的作者别名映射数量。\n"
                "可用于评估归并阶段实际收益。"
            ),
            2,
            2,
        )
        g.addWidget(self.lbl_last_mapped, 2, 3)
        g.addWidget(
            self._tip_label(
                "更新记录数",
                "本次运行中被实际更新的记录数。\n"
                "若为 0，通常表示本次是纯复用状态。"
            ),
            3,
            0,
        )
        g.addWidget(self.lbl_last_updated, 3, 1)
        g.addWidget(
            self._tip_label(
                "作者分组数",
                "上次运行得到的作者分组数量。\n"
                "用于观察归并规则是否导致分组变化。"
            ),
            3,
            2,
        )
        g.addWidget(self.lbl_last_author_buckets, 3, 3)
        g.addWidget(
            self._tip_label(
                "新增作品数",
                "增量模式下 parse_new_or_changed 的数量。\n"
                "可用于确认本次是否确实处理了新作品。"
            ),
            4,
            0,
        )
        g.addWidget(self.lbl_last_parse_new, 4, 1)
        return frame

    @staticmethod
    def _tip_label(text: str, tip: str) -> QLabel:
        label = QLabel(text)
        label.setToolTip(tip)
        return label

    def _build_actions(self, parent: QVBoxLayout) -> None:
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        v = QVBoxLayout(frame)
        title = QLabel("执行与结果")
        title.setToolTip(
            "运行控制与结果文件入口。\n"
            "可在任务结束后一键打开 Excel、HTML、JSON、统计文件。"
        )
        v.addWidget(title)

        row = QHBoxLayout()
        self.btn_run = QPushButton("开始运行")
        self.btn_stop = QPushButton("停止")
        self.btn_save = QPushButton("保存参数")
        self.btn_run.setToolTip("开始执行归档、去重、导出流程。")
        self.btn_stop.setToolTip("请求停止当前任务；再次点击将强制终止。")
        self.btn_save.setToolTip("将当前界面参数保存到 gui_config.json。")
        self.btn_stop.setStyleSheet(
            "QPushButton { background:#d14343; }"
            "QPushButton:hover { background:#e05656; }"
            "QPushButton:disabled { background:#d8b4b4; color:#f6f6f6; }"
        )
        self.btn_stop.setEnabled(False)
        self.btn_run.clicked.connect(self._start)
        self.btn_stop.clicked.connect(self._stop)
        self.btn_save.clicked.connect(lambda: self._save_config(False))
        row.addWidget(self.btn_run)
        row.addWidget(self.btn_stop)
        row.addWidget(self.btn_save)
        row.addStretch(1)
        v.addLayout(row)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        self.progress.setToolTip(
            "综合进度条（Parse / AuthorMerge / DeepSeek 加权）。\n"
            "失败时会变为红色并显示 exit code。"
        )
        v.addWidget(self.progress)

        g = QGridLayout()
        self.btn_open_dir = QPushButton("打开结果目录")
        self.btn_xlsx = QPushButton("打开 Excel")
        self.btn_html = QPushButton("打开 HTML")
        self.btn_json = QPushButton("打开 JSON")
        self.btn_stats = QPushButton("打开统计 JSON")
        self.btn_open_dir.setToolTip("打开当前输出目录。")
        self.btn_xlsx.setToolTip("打开 Excel 审核表（作品归档结果.xlsx）。")
        self.btn_html.setToolTip("打开 HTML 审核页（作品归档审核页.html）。")
        self.btn_json.setToolTip("打开结构化结果（作品归档结果.json）。")
        self.btn_stats.setToolTip("打开统计结果（作品归档统计.json）。")
        self.btn_open_dir.clicked.connect(self._open_dir)
        self.btn_xlsx.clicked.connect(lambda: self._open_file("作品归档结果.xlsx"))
        self.btn_html.clicked.connect(lambda: self._open_file("作品归档审核页.html"))
        self.btn_json.clicked.connect(lambda: self._open_file("作品归档结果.json"))
        self.btn_stats.clicked.connect(lambda: self._open_file("作品归档统计.json"))
        g.addWidget(self.btn_open_dir, 0, 0)
        g.addWidget(self.btn_xlsx, 0, 1)
        g.addWidget(self.btn_html, 0, 2)
        g.addWidget(self.btn_json, 0, 3)
        g.addWidget(self.btn_stats, 0, 4)
        v.addLayout(g)
        parent.addWidget(frame)
