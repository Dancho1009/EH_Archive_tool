from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame, QScrollArea, QSplitter, QVBoxLayout, QWidget

from .layout_sections import GuiLayoutSectionsMixin
from .layout_theme import GuiLayoutThemeMixin


class GuiLayoutMixin(GuiLayoutSectionsMixin, GuiLayoutThemeMixin):
    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        split = QSplitter(Qt.Horizontal)
        split.setHandleWidth(6)
        split.setChildrenCollapsible(False)
        split.setOpaqueResize(False)
        root.addWidget(split)
        self.main_splitter = split

        left = QWidget()
        right = QWidget()
        left.setMinimumWidth(420)
        right.setMinimumWidth(420)
        split.addWidget(left)
        split.addWidget(right)
        split.setSizes([760, 500])
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)
        split.splitterMoved.connect(self._remember_main_splitter_sizes)
        self._main_splitter_user_sizes = split.sizes()

        l = QVBoxLayout(left)
        r = QVBoxLayout(right)
        r.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(8)
        r.setSpacing(8)

        l.addWidget(self._create_roots_frame())
        self.left_log_err_splitter = QSplitter(Qt.Vertical)
        self.left_log_err_splitter.setHandleWidth(6)
        self.left_log_err_splitter.setChildrenCollapsible(False)
        self.left_log_err_splitter.setOpaqueResize(True)
        self.left_log_err_splitter.addWidget(self._create_log_frame())
        self.left_log_err_splitter.addWidget(self._create_err_frame())
        self.left_log_err_splitter.setStretchFactor(0, 1)
        self.left_log_err_splitter.setStretchFactor(1, 0)
        self.left_log_err_splitter.setSizes([560, 160])
        l.addWidget(self.left_log_err_splitter, 1)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.NoFrame)
        r.addWidget(right_scroll)

        right_content = QWidget()
        right_scroll.setWidget(right_content)
        rr = QVBoxLayout(right_content)
        rr.setContentsMargins(0, 0, 0, 0)
        rr.setSpacing(8)

        self._build_opts(rr)
        self._build_info_tabs(rr)
        self._build_actions(rr)
        rr.addStretch(1)

    def _remember_main_splitter_sizes(self, *_args) -> None:
        if getattr(self, "_adjusting_splitter", False) or getattr(self, "_window_resizing", False):
            return
        if hasattr(self, "main_splitter"):
            sizes = self.main_splitter.sizes()
            if len(sizes) >= 2:
                self._main_splitter_user_sizes = [int(sizes[0]), int(sizes[1])]
