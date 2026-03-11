from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QDoubleValidator, QIntValidator
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class GuiOptionsPanelMixin:
    def _build_opts(self, parent: QVBoxLayout) -> None:
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        v = QVBoxLayout(frame)
        v.addWidget(QLabel("运行参数"))

        self._init_option_widgets()

        basic_form = QFormLayout()
        basic_form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        self._fill_basic_form(basic_form)
        v.addLayout(basic_form)

        self.advanced_toggle_btn = QToolButton()
        self.advanced_toggle_btn.setText("展开高级参数")
        self.advanced_toggle_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.advanced_toggle_btn.setCheckable(True)
        self.advanced_toggle_btn.setToolTip(
            "点击展开或收起高级参数区域。\n"
            "高级参数主要用于大库、复杂归并和精细化 DeepSeek 调优。\n"
            "日常场景可只用基础参数。"
        )
        self.advanced_toggle_btn.toggled.connect(self._toggle_advanced_options)
        v.addWidget(self.advanced_toggle_btn)

        self.advanced_group = QGroupBox("高级参数")
        self.advanced_group.setToolTip(
            "包含作者归并、系列提取、簇复判、社团建议等高级开关与阈值。\n"
            "建议先用默认值跑通，再按结果逐项调整。"
        )
        self.advanced_group.setVisible(False)
        advanced_form = QFormLayout(self.advanced_group)
        advanced_form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        self._fill_advanced_form(advanced_form)
        v.addWidget(self.advanced_group)

        parent.addWidget(frame)
        self._sync_state()
        self._sync_tips()
        self._update_deep()
        self._toggle_advanced_options(False)

    def _init_option_widgets(self) -> None:
        self.output_edit = QLineEdit(self.default_output)
        self.output_edit.textChanged.connect(self._on_output_changed)

        self.recursive_chk = QCheckBox("递归扫描 --recursive")
        self.full_rebuild_chk = QCheckBox("全量重建 --full-rebuild")
        self.full_rebuild_chk.setChecked(True)
        self.incremental_chk = QCheckBox("增量 --incremental")
        self.freeze_existing_chk = QCheckBox("冻结存量 --freeze-existing")
        self.use_deepseek_chk = QCheckBox("启用 DeepSeek --use-deepseek")
        self.use_deepseek_chk.setChecked(True)

        self.series_extract_ds_chk = QCheckBox("系列提取增强 --deepseek-series-extract")
        self.author_merge_chk = QCheckBox("作者归并 --deepseek-author-merge")
        self.author_merge_chk.setChecked(True)
        self.series_missing_ds_chk = QCheckBox("系列缺失复核 --deepseek-series-missing")
        self.cluster_refine_chk = QCheckBox("重复簇复判 --deepseek-cluster-refine")
        self.circle_author_suggest_chk = QCheckBox("社团作者建议 --deepseek-circle-author-suggest")

        self.full_rebuild_chk.toggled.connect(self._on_mode_toggle)
        self.incremental_chk.toggled.connect(self._on_mode_toggle)
        self.use_deepseek_chk.toggled.connect(self._update_deep)
        self.series_extract_ds_chk.toggled.connect(self._update_deep)
        self.author_merge_chk.toggled.connect(self._update_deep)
        self.series_missing_ds_chk.toggled.connect(self._update_deep)
        self.cluster_refine_chk.toggled.connect(self._update_deep)
        self.circle_author_suggest_chk.toggled.connect(self._update_deep)

        self.merge_policy_edit = QLineEdit("")
        self.merge_policy_edit.setPlaceholderText("留空时使用 输出目录/merge_policy.json")

        self.api_key_edit = QLineEdit("")
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_visible = False
        self.btn_toggle_api = QPushButton("显示")
        self.btn_toggle_api.setFixedWidth(52)
        self.btn_toggle_api.clicked.connect(self._toggle_api_key_visibility)

        self.model_combo = QComboBox()
        self.model_combo.addItems(["deepseek-chat", "deepseek-reasoner"])
        self.candidate_mode_combo = QComboBox()
        self.candidate_mode_combo.addItem("严格", "strict")
        self.candidate_mode_combo.addItem("均衡", "balanced")
        self.candidate_mode_combo.addItem("激进", "aggressive")
        self.candidate_mode_combo.setCurrentIndex(1)

        self.timeout_edit = QLineEdit("45")
        self.retries_edit = QLineEdit("3")
        self.retry_sleep_edit = QLineEdit("2")
        self.deepseek_max_candidates_edit = QLineEdit("-1")
        self.merge_batch_edit = QLineEdit("10")
        self.merge_max_names_edit = QLineEdit("-1")
        self.merge_stop_fail_edit = QLineEdit("5")
        self.series_extract_max_edit = QLineEdit("-1")
        self.series_extract_min_conf_edit = QLineEdit("70")
        self.series_max_groups_edit = QLineEdit("-1")
        self.cluster_max_groups_edit = QLineEdit("-1")
        self.cluster_max_size_edit = QLineEdit("12")
        self.circle_author_max_circles_edit = QLineEdit("-1")
        self.circle_author_batch_edit = QLineEdit("25")
        self.circle_author_min_conf_edit = QLineEdit("70")
        self.history_keep_edit = QLineEdit("3")

        self.timeout_edit.setValidator(QIntValidator(1, 3600, self))
        self.retries_edit.setValidator(QIntValidator(0, 20, self))
        self.retry_sleep_edit.setValidator(QDoubleValidator(0.0, 120.0, 2, self))
        self.deepseek_max_candidates_edit.setValidator(QIntValidator(-1, 500000, self))
        self.merge_batch_edit.setValidator(QIntValidator(1, 500, self))
        self.merge_max_names_edit.setValidator(QIntValidator(-1, 200000, self))
        self.merge_stop_fail_edit.setValidator(QIntValidator(1, 50, self))
        self.series_extract_max_edit.setValidator(QIntValidator(-1, 500000, self))
        self.series_extract_min_conf_edit.setValidator(QIntValidator(0, 100, self))
        self.series_max_groups_edit.setValidator(QIntValidator(-1, 500000, self))
        self.cluster_max_groups_edit.setValidator(QIntValidator(-1, 5000, self))
        self.cluster_max_size_edit.setValidator(QIntValidator(3, 100, self))
        self.circle_author_max_circles_edit.setValidator(QIntValidator(-1, 200000, self))
        self.circle_author_batch_edit.setValidator(QIntValidator(1, 500, self))
        self.circle_author_min_conf_edit.setValidator(QIntValidator(0, 100, self))
        self.history_keep_edit.setValidator(QIntValidator(0, 999, self))

    def _fill_basic_form(self, form: QFormLayout) -> None:
        btn_output = QPushButton("浏览")
        btn_output.setToolTip("选择结果输出目录。")
        btn_output.clicked.connect(self._choose_output)
        btn_output_copy = QPushButton("复制")
        btn_output_copy.setToolTip("复制输出目录路径到剪贴板。")
        btn_output_copy.clicked.connect(lambda: self._copy_text(self.output_edit.text()))
        out_row = QHBoxLayout()
        out_row.addWidget(self.output_edit)
        out_row.addWidget(btn_output)
        out_row.addWidget(btn_output_copy)
        form.addRow(
            self._tip_label(
                "输出目录",
                "作用：定义本次运行产物的保存位置。\n"
                "会输出：Excel、HTML、JSON、统计 JSON、状态文件、运行历史等。\n"
                "建议：单独建一个 result 目录，便于后续审核与备份。",
            ),
            self._wrap(out_row),
        )

        form.addRow(
            "",
            self._wrap_check_row(
                self.recursive_chk,
                "递归扫描 --recursive",
                "作用：是否扫描子目录。\n"
                "开启后会扫描所有层级，适合目录结构复杂的库。\n"
                "关闭时只扫描根目录第一层，速度更快。",
            ),
        )
        form.addRow(
            "",
            self._wrap_check_row(
                self.full_rebuild_chk,
                "全量重建 --full-rebuild",
                "作用：忽略状态文件，重新解析全部作品并重做归并/去重。\n"
                "适用：首次整理、规则更新、历史结果明显异常。\n"
                "影响：耗时最长，但结果最完整。",
            ),
        )
        form.addRow(
            "",
            self._wrap_check_row(
                self.incremental_chk,
                "增量 --incremental",
                "作用：仅处理新增或变更作品。\n"
                "适用：日常维护更新。\n"
                "影响：速度快，但依赖 archive_state.json 的历史快照。",
            ),
        )
        form.addRow(
            "",
            self._wrap_check_row(
                self.freeze_existing_chk,
                "冻结存量 --freeze-existing",
                "作用：增量模式下，保持存量记录判定不变，仅处理新增/变更记录。\n"
                "适用：存量已经人工审核完成，不希望再次扰动。\n"
                "注意：只在勾选“增量”时生效。",
            ),
        )
        form.addRow(
            "",
            self._wrap_check_row(
                self.use_deepseek_chk,
                "启用 DeepSeek --use-deepseek",
                "作用：启用语义能力辅助归并与复判。\n"
                "收益：提升跨语言别名、复杂重复关系识别准确率。\n"
                "代价：增加耗时和 API 成本。",
            ),
        )

        btn_policy = QPushButton("浏览")
        btn_policy.setToolTip("选择归并策略文件（JSON）。")
        btn_policy.clicked.connect(self._choose_merge_policy)
        btn_policy_copy = QPushButton("复制")
        btn_policy_copy.setToolTip("复制策略文件路径到剪贴板。")
        btn_policy_copy.clicked.connect(lambda: self._copy_text(self.merge_policy_edit.text()))
        policy_row = QHBoxLayout()
        policy_row.addWidget(self.merge_policy_edit)
        policy_row.addWidget(btn_policy)
        policy_row.addWidget(btn_policy_copy)
        form.addRow(
            self._tip_label(
                "归并策略文件",
                "作用：人工指定作者/社团归并规则。\n"
                "支持：白名单、黑名单、社团到作者映射、歧义社团、冻结作者。\n"
                "留空：自动读取 输出目录/merge_policy.json。",
            ),
            self._wrap(policy_row),
        )

        form.addRow(
            self._tip_label(
                "历史保留份数",
                "作用：保留最近 N 份结果快照。\n"
                "0=不保留；建议 3~10，便于回滚和比对。",
            ),
            self.history_keep_edit,
        )

    def _fill_advanced_form(self, form: QFormLayout) -> None:
        api_row = QHBoxLayout()
        api_row.addWidget(self.api_key_edit)
        api_row.addWidget(self.btn_toggle_api)
        form.addRow(
            self._tip_label(
                "DeepSeek API Key",
                "作用：用于调用 DeepSeek API。\n"
                "留空时将读取系统环境变量 DEEPSEEK_API_KEY。\n"
                "建议：优先用环境变量管理，避免明文泄露。",
            ),
            self._wrap(api_row),
        )
        form.addRow(
            self._tip_label(
                "DeepSeek 模型",
                "deepseek-chat：速度更稳、成本更低，适合常规批量。\n"
                "deepseek-reasoner：推理更强，适合疑难样本复核。\n"
                "建议：默认先用 deepseek-chat。",
            ),
            self.model_combo,
        )
        form.addRow(
            self._tip_label(
                "候选模式",
                "严格：仅提交高置信候选，结果更保守，误判更少。\n"
                "均衡：准确率与召回率平衡，适合大多数场景（推荐）。\n"
                "激进：尽可能扩大召回，能找到更多候选，但误判和成本会增加。",
            ),
            self.candidate_mode_combo,
        )
        form.addRow(
            self._tip_label(
                "语义复判最大候选数",
                "作用：DeepSeek 语义复判阶段最多处理的候选作品数。\n"
                "-1=自动（按当前候选池全量处理）；0=不处理。\n"
                "其他数值=按填写的上限截断处理。",
            ),
            self.deepseek_max_candidates_edit,
        )
        form.addRow(
            self._tip_label(
                "超时（秒）",
                "作用：单次 API 请求超时时间。\n"
                "建议：30~90；网络不稳定可适当调高。",
            ),
            self.timeout_edit,
        )
        form.addRow(
            self._tip_label(
                "重试次数",
                "作用：请求失败后的自动重试次数。\n"
                "建议：2~5；次数越高，容错越好但耗时更长。",
            ),
            self.retries_edit,
        )
        form.addRow(
            self._tip_label(
                "重试等待（秒）",
                "作用：重试前基础等待时间（指数退避基值）。\n"
                "建议：1~3 秒；网络抖动时可适当增大。",
            ),
            self.retry_sleep_edit,
        )

        form.addRow(
            "",
            self._wrap_check_row(
                self.series_extract_ds_chk,
                "系列提取增强 --deepseek-series-extract",
                "作用：用 DeepSeek 补充系列标题与系列序号提取。\n"
                "适用：本地规则难以稳定识别卷次/话次的作品库。\n"
                "配套参数：系列提取最大作品数、系列提取最小置信度。",
            ),
        )
        form.addRow(
            "",
            self._wrap_check_row(
                self.author_merge_chk,
                "作者归并 --deepseek-author-merge",
                "作用：将中/日/罗马字等别名归并到同一作者桶。\n"
                "收益：减少同一作者被拆分导致的去重漏判。\n"
                "代价：API 调用较多，耗时较长。",
            ),
        )
        form.addRow(
            "",
            self._wrap_check_row(
                self.series_missing_ds_chk,
                "系列缺失复核 --deepseek-series-missing",
                "作用：对本地系列缺失候选做语义复核。\n"
                "收益：补充规则难命中的缺失卷/话。\n"
                "建议：全量跑或新增较多时启用。",
            ),
        )
        form.addRow(
            "",
            self._wrap_check_row(
                self.cluster_refine_chk,
                "重复簇复判 --deepseek-cluster-refine",
                "作用：按“重复簇”整组提交，统一选择主本并给出风险说明。\n"
                "收益：降低互相标记、误把系列章节判成重复的概率。\n"
                "建议：重复误判较多时启用。",
            ),
        )
        form.addRow(
            "",
            self._wrap_check_row(
                self.circle_author_suggest_chk,
                "社团作者建议 --deepseek-circle-author-suggest",
                "作用：根据共现关系给出社团->作者建议映射。\n"
                "输出：用于人工审核，不会直接改主数据。\n"
                "适用：有大量“仅社团名”作品的库。",
            ),
        )

        form.addRow(
            self._tip_label(
                "作者归并批大小",
                "作用：作者归并每次提交给 DeepSeek 的名称数量。\n"
                "较大：批次少但更易超时；较小：更稳但批次多。\n"
                "建议：10~50。",
            ),
            self.merge_batch_edit,
        )
        form.addRow(
            self._tip_label(
                "作者归并最大名称数",
                "作用：作者归并阶段最多处理多少个唯一名称。\n"
                "-1=自动（按当前候选全量处理）。\n"
                "其他数值=按填写上限处理；值越大覆盖越全、耗时和成本越高。",
            ),
            self.merge_max_names_edit,
        )
        form.addRow(
            self._tip_label(
                "归并连续失败终止阈值",
                "作用：连续失败批次数达到阈值后提前停止归并阶段。\n"
                "收益：避免长时间卡死。\n"
                "建议：3~8。",
            ),
            self.merge_stop_fail_edit,
        )
        form.addRow(
            self._tip_label(
                "系列提取最大作品数",
                "作用：系列提取阶段最多送审的候选作品数。\n"
                "-1=自动（按当前候选全量处理）；0=不处理。\n"
                "其他数值=按填写上限处理。",
            ),
            self.series_extract_max_edit,
        )
        form.addRow(
            self._tip_label(
                "系列提取最小置信度",
                "作用：低于该置信度的系列提取结果不回写。\n"
                "值越高越保守。\n"
                "建议：65~85。",
            ),
            self.series_extract_min_conf_edit,
        )
        form.addRow(
            self._tip_label(
                "系列复核最大分组数",
                "作用：系列缺失复核处理上限。\n"
                "-1=自动等于候选分组数；其他正整数=手动上限。\n"
                "建议：默认 -1。",
            ),
            self.series_max_groups_edit,
        )
        form.addRow(
            self._tip_label(
                "簇复判最大分组数",
                "作用：重复簇复判最多处理的分组数量。\n"
                "-1=自动（按当前候选分组全量处理）；0=不处理。\n"
                "其他数值=按填写上限处理。",
            ),
            self.cluster_max_groups_edit,
        )
        form.addRow(
            self._tip_label(
                "簇复判分组最大作品数",
                "作用：单个簇允许提交的最大作品数。\n"
                "过大容易超时。\n"
                "建议：8~20。",
            ),
            self.cluster_max_size_edit,
        )
        form.addRow(
            self._tip_label(
                "社团建议最大社团数",
                "作用：社团作者建议阶段最多处理的社团数。\n"
                "-1=自动（按当前候选社团全量处理）；0=不处理。\n"
                "其他数值=按填写上限处理；值越大覆盖越高、耗时和成本越高。",
            ),
            self.circle_author_max_circles_edit,
        )
        form.addRow(
            self._tip_label(
                "社团建议批大小",
                "作用：每批提交多少社团给 DeepSeek。\n"
                "建议：10~50；网络不稳时降低更稳。",
            ),
            self.circle_author_batch_edit,
        )
        form.addRow(
            self._tip_label(
                "社团建议最小置信度",
                "作用：低于该置信度的建议不会进入建议映射。\n"
                "建议：60~85，值越高越保守。",
            ),
            self.circle_author_min_conf_edit,
        )

    @staticmethod
    def _wrap(layout: QHBoxLayout) -> QWidget:
        widget = QWidget()
        widget.setLayout(layout)
        return widget

    @staticmethod
    def _wrap_check_row(widget: QCheckBox, label_text: str, tip: str) -> QWidget:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        widget.setText("")
        row.addWidget(widget)
        label = QLabel(label_text)
        label.setToolTip(tip)
        row.addWidget(label)
        row.addStretch(1)
        return GuiOptionsPanelMixin._wrap(row)

    @staticmethod
    def _tip_label(text: str, tip: str) -> QLabel:
        label = QLabel(text)
        label.setToolTip(tip)
        return label

    def _toggle_advanced_options(self, checked: bool) -> None:
        self.advanced_group.setVisible(checked)
        self.advanced_toggle_btn.setText("收起高级参数" if checked else "展开高级参数")
