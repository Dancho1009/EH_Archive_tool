from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication, QComboBox, QLabel


class GuiLayoutThemeMixin:
    def _apply_beauty_theme(self) -> None:
        QApplication.instance().setStyle("Fusion")
        QApplication.instance().setFont(QFont("Microsoft YaHei UI", 10))
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #f4f6f9;
                color: #1f2937;
            }
            QFrame {
                background: #ffffff;
                border: 1px solid #d9e0ea;
                border-radius: 8px;
            }
            QLabel {
                background: transparent;
                border: none;
            }
            QLineEdit, QPlainTextEdit, QListWidget, QComboBox {
                background: #fcfdff;
                border: 1px solid #cfd8e3;
                border-radius: 6px;
                padding: 4px 6px;
            }
            QPushButton {
                background: #2f6fe4;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background: #3d7bef;
            }
            QPushButton:pressed {
                background: #245ec8;
            }
            QPushButton:disabled {
                background: #9aa9bf;
                color: #e9edf3;
            }
            QCheckBox {
                spacing: 6px;
                background: transparent;
                border: none;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #94a3b8;
                border-radius: 3px;
                background: #ffffff;
            }
            QCheckBox::indicator:checked {
                background: #2f6fe4;
                border: 1px solid #2f6fe4;
            }
            QProgressBar {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                text-align: center;
                background: #f8fafc;
            }
            QProgressBar::chunk {
                background: #16a34a;
                border-radius: 6px;
            }
            QSplitter::handle {
                background: #dde4ee;
            }
            QToolTip {
                background-color: #1f2937;
                color: #ffffff;
                border: 1px solid #4b5563;
                padding: 4px 6px;
            }
            """
        )
        self._apply_log_fonts()
        self._enable_copyable_non_button_text()

    def _enable_copyable_non_button_text(self) -> None:
        # Make non-button labels copyable (field names, section titles, stats text).
        for label in self.findChildren(QLabel):
            label.setTextInteractionFlags(
                label.textInteractionFlags() | Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
            )
        # Keep combo selectable while preventing arbitrary input.
        for combo in self.findChildren(QComboBox):
            if not combo.isEditable():
                combo.setEditable(True)
            line = combo.lineEdit()
            if line is not None:
                line.setReadOnly(True)
                line.setCursorPosition(0)
