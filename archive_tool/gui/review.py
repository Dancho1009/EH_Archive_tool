from __future__ import annotations

import json
from pathlib import Path

from PyQt5.QtCore import QObject, Qt, QUrl, pyqtSlot
from PyQt5.QtWidgets import QLabel, QMainWindow

from ..review.actions import delete_and_sync

try:
    from PyQt5.QtWebChannel import QWebChannel
    from PyQt5.QtWebEngineWidgets import QWebEngineView
except Exception:
    QWebChannel = None  # type: ignore[assignment]
    QWebEngineView = None  # type: ignore[assignment]


class ReviewBridge(QObject):
    def __init__(self, output_dir: Path, state_file: Path, log_cb) -> None:
        super().__init__()
        self.output_dir = output_dir
        self.state_file = state_file
        self.log_cb = log_cb

    @pyqtSlot(str, result=str)
    def deletePaths(self, paths_json: str) -> str:  # noqa: N802 - Qt slot name
        try:
            arr = json.loads(paths_json or "[]")
            if not isinstance(arr, list):
                arr = []
            paths = [str(x or "") for x in arr]
            ret = delete_and_sync(
                paths,
                output_dir=self.output_dir,
                state_file=self.state_file,
                source="qt-bridge",
                quick_reexport=True,
            )
            self.log_cb(
                f"[Review] delete requested={len(paths)} deleted={len(ret.get('deleted', []))} "
                f"failed={len(ret.get('failed', []))} state_removed="
                f"{(ret.get('state_sync') or {}).get('removed_records', 0)} "
                f"reexport={'ok' if (ret.get('reexport') or {}).get('ok') else 'fail'}\n"
            )
            return json.dumps(ret, ensure_ascii=False)
        except Exception as exc:
            ret = {"ok": False, "deleted": [], "missing": [], "failed": [{"path": "", "error": str(exc)}]}
            self.log_cb(f"[Review][ERROR] {exc}\n")
            return json.dumps(ret, ensure_ascii=False)


class ReviewWindow(QMainWindow):
    def __init__(self, html_path: Path, output_dir: Path, state_file: Path, log_cb, on_close=None) -> None:
        super().__init__()
        self.setWindowTitle("作品归档审核（内嵌）")
        self.resize(1400, 900)
        self._on_close = on_close
        if QWebEngineView is None or QWebChannel is None:
            label = QLabel("当前环境缺少 PyQtWebEngine，无法内嵌审核页。")
            label.setAlignment(Qt.AlignCenter)
            self.setCentralWidget(label)
            return
        self.view = QWebEngineView(self)
        self.setCentralWidget(self.view)
        self.bridge = ReviewBridge(output_dir=output_dir, state_file=state_file, log_cb=log_cb)
        channel = QWebChannel(self.view.page())
        channel.registerObject("reviewBridge", self.bridge)
        self.view.page().setWebChannel(channel)
        self.view.setUrl(QUrl.fromLocalFile(str(html_path.resolve())))

    def closeEvent(self, event) -> None:  # type: ignore[override]
        try:
            if callable(self._on_close):
                g = self.normalGeometry() if self.isMaximized() else self.geometry()
                self._on_close(g, bool(self.isMaximized()))
        finally:
            super().closeEvent(event)
