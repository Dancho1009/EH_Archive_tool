from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.fonts.warning=false")

if os.name == "nt":
    from ctypes import wintypes

from PyQt5.QtCore import QProcess, QRect, QTimer
from PyQt5.QtGui import QResizeEvent
from PyQt5.QtWidgets import QApplication, QMainWindow

from .mixins import (
    GuiLayoutMixin,
    GuiLoggingMixin,
    GuiOptionsPanelMixin,
    GuiPathMixin,
    GuiPersistMixin,
    GuiResultMixin,
    GuiRunnerMixin,
)
from .review import ReviewWindow as EmbeddedReviewWindow

WM_ENTERSIZEMOVE = 0x0231
WM_EXITSIZEMOVE = 0x0232
WM_SIZING = 0x0214
WMSZ_LEFT = 1
WMSZ_RIGHT = 2
WMSZ_TOPLEFT = 4
WMSZ_TOPRIGHT = 5
WMSZ_BOTTOMLEFT = 7
WMSZ_BOTTOMRIGHT = 8


class ArchiveGui(
    GuiPersistMixin,
    GuiResultMixin,
    GuiRunnerMixin,
    GuiPathMixin,
    GuiLoggingMixin,
    GuiOptionsPanelMixin,
    GuiLayoutMixin,
    QMainWindow,
):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("作品归档与查重 GUI (PyQt)")
        self.resize(1220, 760)

        self.base_dir = Path(__file__).resolve().parents[2]
        self.script_path = self.base_dir / "archive_works.py"
        self.default_output = str((self.base_dir / "result").resolve())
        self.state_file_path = str((self.base_dir / "result" / "archive_state.json").resolve())
        self.config_path = self.base_dir / "result" / "gui_config.json"
        self.legacy_config_path = Path(__file__).resolve().parent.parent / "result" / "gui_config.json"
        self.last_browse_dir = self.default_output

        self.proc = None
        self.review_server_proc = None
        self.review_window: EmbeddedReviewWindow | None = None
        self.review_window_rect: QRect | None = None
        self.review_window_maximized = False
        self.run_started_at: float | None = None
        self.stop_requested = False

        self.max_log_lines = 6000
        self._log_lines: list[str] = []
        self._progress_lines: dict[str, str] = {}
        self._last_rendered_log = ""
        self.error_seen: set[str] = set()
        self.error_count = 0
        self.stage_progress = {"Parse": 0.0, "AuthorMerge": 0.0, "DeepSeek": 0.0}
        self.stage_weights = {"Parse": 0.6, "AuthorMerge": 0.2, "DeepSeek": 0.2}
        self._stream_buffer = ""

        self._last_window_geometry: QRect | None = None
        self._adjusting_splitter = False
        self._window_resizing = False
        self._resize_anchor_mode: str | None = None
        self._native_resize_anchor: str | None = None
        self._resize_end_timer = QTimer(self)
        self._resize_end_timer.setSingleShot(True)
        self._resize_end_timer.timeout.connect(self._finish_resize_sequence)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick_elapsed)

        self._build_ui()
        self._apply_beauty_theme()
        self._load_config()
        if not self.api_key_edit.text().strip():
            self.api_key_edit.setText(os.environ.get("DEEPSEEK_API_KEY", "").strip())
        self._update_result_buttons()
        self._load_output_stats()
        QTimer.singleShot(0, self._capture_layout_baseline)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        try:
            self._save_config(True)
            if self.review_window:
                self.review_window.close()
            if self.review_server_proc and self.review_server_proc.state() != QProcess.NotRunning:
                self.review_server_proc.terminate()
                if not self.review_server_proc.waitForFinished(1000):
                    self.review_server_proc.kill()
        finally:
            super().closeEvent(event)

    def nativeEvent(self, eventType, message):  # type: ignore[override]
        if os.name == "nt":
            try:
                msg = wintypes.MSG.from_address(int(message))
                m = int(msg.message)
                if m == WM_ENTERSIZEMOVE:
                    self._native_resize_anchor = None
                    self._resize_anchor_mode = None
                elif m == WM_EXITSIZEMOVE:
                    self._native_resize_anchor = None
                    self._resize_anchor_mode = None
                elif m == WM_SIZING:
                    edge = int(msg.wParam)
                    if edge in {WMSZ_LEFT, WMSZ_TOPLEFT, WMSZ_BOTTOMLEFT}:
                        self._native_resize_anchor = "keep_right"
                    elif edge in {WMSZ_RIGHT, WMSZ_TOPRIGHT, WMSZ_BOTTOMRIGHT}:
                        self._native_resize_anchor = "keep_left"
                    else:
                        self._native_resize_anchor = None
            except Exception:
                pass
        try:
            return super().nativeEvent(eventType, message)
        except Exception:
            return False, 0

    def resizeEvent(self, event: QResizeEvent) -> None:  # type: ignore[override]
        self._window_resizing = True
        try:
            super().resizeEvent(event)
            self._adjust_splitter_for_edge_resize()
            self._resize_end_timer.start(120)
        finally:
            self._window_resizing = False

    def _capture_layout_baseline(self) -> None:
        if hasattr(self, "_remember_main_splitter_sizes"):
            self._remember_main_splitter_sizes()
        self._last_window_geometry = QRect(self.geometry())

    def _finish_resize_sequence(self) -> None:
        self._resize_anchor_mode = None
        self._native_resize_anchor = None
        if hasattr(self, "_remember_main_splitter_sizes"):
            self._remember_main_splitter_sizes()
        self._last_window_geometry = QRect(self.geometry())

    def _adjust_splitter_for_edge_resize(self) -> None:
        if self._adjusting_splitter or not hasattr(self, "main_splitter"):
            self._last_window_geometry = QRect(self.geometry())
            return

        current = QRect(self.geometry())
        previous = self._last_window_geometry
        if previous is None:
            self._last_window_geometry = current
            return

        if self.isMaximized() or self.isFullScreen():
            self._last_window_geometry = current
            return

        dw = int(current.width() - previous.width())
        dx = int(current.x() - previous.x())
        if dw == 0:
            self._last_window_geometry = current
            return

        sizes = self.main_splitter.sizes()
        if len(sizes) < 2:
            self._last_window_geometry = current
            return

        left_min = max(320, self.main_splitter.widget(0).minimumWidth())
        right_min = max(320, self.main_splitter.widget(1).minimumWidth())
        total = max(left_min + right_min, int(sizes[0] + sizes[1]))

        pref = getattr(self, "_main_splitter_user_sizes", sizes)
        pref_left = int(pref[0]) if len(pref) >= 2 else int(sizes[0])
        pref_right = int(pref[1]) if len(pref) >= 2 else int(sizes[1])

        def _clamp(v: int, lo: int, hi: int) -> int:
            return max(lo, min(v, hi))

        prev_left = int(previous.x())
        prev_right = int(previous.x() + previous.width())
        cur_left = int(current.x())
        cur_right = int(current.x() + current.width())
        left_move = abs(cur_left - prev_left)
        right_move = abs(cur_right - prev_right)

        if self._native_resize_anchor in {"keep_left", "keep_right"}:
            self._resize_anchor_mode = self._native_resize_anchor
        elif self._resize_anchor_mode is None:
            dominance_gap = 3
            # 左边框拖动：左边缘位移显著大于右边缘位移 -> 保持右侧宽度
            if left_move >= right_move + dominance_gap:
                self._resize_anchor_mode = "keep_right"
            # 右边框拖动：右边缘位移显著大于左边缘位移 -> 保持左侧宽度
            elif right_move >= left_move + dominance_gap:
                self._resize_anchor_mode = "keep_left"
            else:
                # 判定不够明确时先不锚定，避免误判导致左右抖动
                self._last_window_geometry = QRect(self.geometry())
                return

        new_left: int | None = None
        new_right: int | None = None
        if self._resize_anchor_mode == "keep_left":
            new_left = _clamp(pref_left, left_min, total - right_min)
            new_right = total - new_left
        elif self._resize_anchor_mode == "keep_right":
            new_right = _clamp(pref_right, right_min, total - left_min)
            new_left = total - new_right

        if new_left is not None and new_right is not None:
            cur_left, cur_right = int(sizes[0]), int(sizes[1])
            if abs(cur_left - new_left) > 1 or abs(cur_right - new_right) > 1:
                self._adjusting_splitter = True
                try:
                    self.main_splitter.setSizes([new_left, new_right])
                finally:
                    self._adjusting_splitter = False

        self._last_window_geometry = QRect(self.geometry())


def main() -> None:
    app = QApplication(sys.argv)
    win = ArchiveGui()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
