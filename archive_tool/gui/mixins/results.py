from __future__ import annotations

import csv
import json
import os
import sys
import webbrowser
from pathlib import Path

from PyQt5.QtCore import QProcess, QRect, QTimer
from PyQt5.QtWidgets import QApplication, QMessageBox

from ..review import ReviewWindow as EmbeddedReviewWindow

try:
    from PyQt5.QtWebChannel import QWebChannel
    from PyQt5.QtWebEngineWidgets import QWebEngineView
except Exception:
    QWebChannel = None  # type: ignore[assignment]
    QWebEngineView = None  # type: ignore[assignment]


class GuiResultMixin:
    def _rpath(self, name: str) -> Path:
        return Path(self.output_edit.text().strip() or self.default_output) / name

    def _latest_match(self, pattern: str) -> Path | None:
        out = Path(self.output_edit.text().strip() or self.default_output)
        files = sorted(out.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        return files[0] if files else None

    def _update_result_buttons(self) -> None:
        self.btn_xlsx.setEnabled(self._latest_match("作品归档结果*.xlsx") is not None)
        self.btn_html.setEnabled(self._rpath("作品归档审核页.html").exists())
        self.btn_json.setEnabled(self._rpath("作品归档结果.json").exists())
        self.btn_stats.setEnabled(self._rpath("作品归档统计.json").exists())

    def _open_dir(self) -> None:
        p = Path(self.output_edit.text().strip() or self.default_output)
        p.mkdir(parents=True, exist_ok=True)
        os.startfile(str(p))

    def _open_file(self, name: str) -> None:
        if name == "作品归档审核页.html":
            self._open_review_html()
            return
        if name == "作品归档结果.xlsx":
            p = self._latest_match("作品归档结果*.xlsx") or self._rpath(name)
        else:
            p = self._rpath(name)
        if not p.exists():
            QMessageBox.warning(self, "文件不存在", f"未找到文件:\n{p}")
            return
        os.startfile(str(p))

    def _open_review_html(self) -> None:
        out_dir = Path(self.output_edit.text().strip() or self.default_output).resolve()
        html_file = out_dir / "作品归档审核页.html"
        if not html_file.exists():
            QMessageBox.warning(self, "文件不存在", f"未找到审核页:\n{html_file}")
            return

        if QWebEngineView is None or QWebChannel is None:
            QMessageBox.warning(
                self,
                "缺少组件",
                "当前环境未安装 PyQtWebEngine，将改为浏览器打开（保留删除能力）。",
            )
            if self._ensure_review_server(out_dir):
                url = "http://127.0.0.1:18765/作品归档审核页.html"
                webbrowser.open(url)
                self._append_log(f"[GUI] 已打开审核页（浏览器回退）: {url}\n")
            else:
                os.startfile(str(html_file))
            return

        state_file = Path(self.state_file_path).resolve()
        self.review_window = EmbeddedReviewWindow(
            html_path=html_file,
            output_dir=out_dir,
            state_file=state_file,
            log_cb=self._append_log,
            on_close=self._on_review_window_closed,
        )
        self._apply_review_window_geometry()
        self.review_window.show()
        if self.review_window_maximized:
            self.review_window.showMaximized()
        self.review_window.raise_()
        self.review_window.activateWindow()
        self._append_log(f"[GUI] 已打开内嵌审核页: {html_file}\n")

    def _on_review_window_closed(self, geom: QRect, maximized: bool) -> None:
        self.review_window_rect = QRect(geom)
        self.review_window_maximized = bool(maximized)
        self.review_window = None
        self._save_config(True)

    def _apply_review_window_geometry(self) -> None:
        if not self.review_window or not self.review_window_rect:
            return
        target = QRect(self.review_window_rect)
        screen = QApplication.primaryScreen()
        if screen is None:
            self.review_window.setGeometry(target)
            return
        avail = screen.availableGeometry()
        if avail.intersects(target):
            self.review_window.setGeometry(target)
            return
        self.review_window.resize(
            max(900, min(target.width(), avail.width())),
            max(600, min(target.height(), avail.height())),
        )

    def _ensure_review_server(self, out_dir: Path) -> bool:
        if self.review_server_proc and self.review_server_proc.state() != QProcess.NotRunning:
            return True
        cmd = [
            sys.executable,
            "-m",
            "archive_tool.review.server",
            "--output-dir",
            str(out_dir),
            "--state-file",
            self.state_file_path,
            "--host",
            "127.0.0.1",
            "--port",
            "18765",
        ]
        self.review_server_proc = QProcess(self)
        self.review_server_proc.setWorkingDirectory(str(self.base_dir))
        self.review_server_proc.setProcessChannelMode(QProcess.MergedChannels)
        self.review_server_proc.start(cmd[0], cmd[1:])
        if not self.review_server_proc.waitForStarted(5000):
            self._append_log("[GUI][WARN] 审核服务启动失败。\n")
            return False
        QTimer.singleShot(250, self._flush_review_server_output)
        return True

    def _flush_review_server_output(self) -> None:
        if not self.review_server_proc:
            return
        data = bytes(self.review_server_proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        if data.strip():
            self._append_log(data if data.endswith("\n") else f"{data}\n")

    def _load_output_stats(self) -> None:
        p = self._rpath("作品归档统计.json")
        targets = [
            self.lbl_total,
            self.lbl_buckets,
            self.lbl_known,
            self.lbl_strict,
            self.lbl_suspect,
            self.lbl_series,
            self.lbl_series_missing,
        ]
        if not p.exists():
            for w in targets:
                w.setText("-")
            self._load_last_run_history()
            return
        try:
            overall = json.loads(p.read_text(encoding="utf-8")).get("overall", {})
            self.lbl_total.setText(str(overall.get("total_records", "-")))
            self.lbl_buckets.setText(str(overall.get("author_buckets", "-")))
            self.lbl_known.setText(str(overall.get("known_authors", "-")))
            self.lbl_strict.setText(str(overall.get("strict_duplicates", "-")))
            self.lbl_suspect.setText(str(overall.get("suspected_duplicates", "-")))
            self.lbl_series.setText(str(overall.get("series_related_non_duplicates", "-")))
            self.lbl_series_missing.setText(str(overall.get("series_missing_records", "-")))
        except Exception:
            for w in targets:
                w.setText("-")
        self._load_last_run_history()

    def _load_last_run_history(self) -> None:
        p = self._rpath("运行历史.csv")
        labels = [
            self.lbl_last_time,
            self.lbl_last_input_names,
            self.lbl_last_cache_hit,
            self.lbl_last_mapped,
            self.lbl_last_updated,
            self.lbl_last_author_buckets,
            self.lbl_last_parse_new,
        ]
        if not p.exists():
            for w in labels:
                w.setText("-")
            return
        try:
            last = None
            with p.open("r", encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    last = row
            if not last:
                for w in labels:
                    w.setText("-")
                return
            self.lbl_last_time.setText(str(last.get("time", "-")))
            self.lbl_last_input_names.setText(str(last.get("input_unique_names", "-")))
            self.lbl_last_cache_hit.setText(str(last.get("author_merge_cache_hit", "-")))
            self.lbl_last_mapped.setText(str(last.get("author_merge_mapped", "-")))
            self.lbl_last_updated.setText(str(last.get("updated_records", "-")))
            self.lbl_last_author_buckets.setText(str(last.get("author_buckets", "-")))
            self.lbl_last_parse_new.setText(str(last.get("parse_new_or_changed", "-")))
        except Exception:
            for w in labels:
                w.setText("-")
