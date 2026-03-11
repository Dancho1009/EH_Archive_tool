from __future__ import annotations

import json

from PyQt5.QtCore import QRect
from PyQt5.QtWidgets import QApplication


class GuiPersistMixin:
    def _save_config(self, silent: bool = False) -> None:
        g = self.normalGeometry() if self.isMaximized() else self.geometry()
        if self.review_window and self.review_window.isVisible():
            rg = self.review_window.normalGeometry() if self.review_window.isMaximized() else self.review_window.geometry()
            rmax = bool(self.review_window.isMaximized())
        elif self.review_window_rect is not None:
            rg = QRect(self.review_window_rect)
            rmax = bool(self.review_window_maximized)
        else:
            rg = None
            rmax = False
        cfg = {
            "roots": self._collect_roots(),
            "output_dir": self.output_edit.text(),
            "recursive": self.recursive_chk.isChecked(),
            "full_rebuild": self.full_rebuild_chk.isChecked(),
            "incremental": self.incremental_chk.isChecked(),
            "freeze_existing": self.freeze_existing_chk.isChecked(),
            "merge_policy_file": self.merge_policy_edit.text().strip(),
            "use_deepseek": self.use_deepseek_chk.isChecked(),
            "series_extract_ds": self.series_extract_ds_chk.isChecked(),
            "author_merge": self.author_merge_chk.isChecked(),
            "series_missing_ds": self.series_missing_ds_chk.isChecked(),
            "cluster_refine": self.cluster_refine_chk.isChecked(),
            "circle_author_suggest": self.circle_author_suggest_chk.isChecked(),
            "candidate_mode": (self.candidate_mode_combo.currentData() or "balanced"),
            "model": self.model_combo.currentText(),
            "deepseek_max_candidates": self.deepseek_max_candidates_edit.text(),
            "timeout": self.timeout_edit.text(),
            "retries": self.retries_edit.text(),
            "retry_sleep": self.retry_sleep_edit.text(),
            "merge_batch_size": self.merge_batch_edit.text(),
            "merge_max_names": self.merge_max_names_edit.text(),
            "merge_stop_fail": self.merge_stop_fail_edit.text(),
            "series_extract_max_candidates": self.series_extract_max_edit.text(),
            "series_extract_min_confidence": self.series_extract_min_conf_edit.text(),
            "series_max_groups": self.series_max_groups_edit.text(),
            "cluster_max_groups": self.cluster_max_groups_edit.text(),
            "cluster_max_size": self.cluster_max_size_edit.text(),
            "circle_author_max_circles": self.circle_author_max_circles_edit.text(),
            "circle_author_batch_size": self.circle_author_batch_edit.text(),
            "circle_author_min_confidence": self.circle_author_min_conf_edit.text(),
            "history_keep": self.history_keep_edit.text(),
            "deepseek_api_key": self.api_key_edit.text().strip(),
            "advanced_opts_expanded": bool(
                getattr(self, "advanced_toggle_btn", None) is not None
                and self.advanced_toggle_btn.isChecked()
            ),
            "last_browse_dir": self.last_browse_dir,
            "main_splitter_sizes": (
                [int(x) for x in self.main_splitter.sizes()]
                if hasattr(self, "main_splitter")
                else None
            ),
            "left_log_err_splitter_sizes": (
                [int(x) for x in self.left_log_err_splitter.sizes()]
                if hasattr(self, "left_log_err_splitter")
                else None
            ),
            "window_x": int(g.x()),
            "window_y": int(g.y()),
            "window_w": int(g.width()),
            "window_h": int(g.height()),
            "window_maximized": bool(self.isMaximized()),
            "review_window_x": int(rg.x()) if rg is not None else None,
            "review_window_y": int(rg.y()) if rg is not None else None,
            "review_window_w": int(rg.width()) if rg is not None else None,
            "review_window_h": int(rg.height()) if rg is not None else None,
            "review_window_maximized": rmax,
        }
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        if not silent:
            self._append_log("[GUI] 参数已保存。\n")

    def _load_config(self) -> None:
        target = self.config_path
        if not target.exists() and self.legacy_config_path.exists():
            target = self.legacy_config_path
        if not target.exists():
            return
        try:
            cfg = json.loads(target.read_text(encoding="utf-8"))
        except Exception:
            return
        self.roots_list.clear()
        [self.roots_list.addItem(p) for p in cfg.get("roots", [])]
        self._dedupe_roots()
        self.output_edit.setText(cfg.get("output_dir", self.default_output))
        self.recursive_chk.setChecked(bool(cfg.get("recursive", False)))
        self.full_rebuild_chk.setChecked(bool(cfg.get("full_rebuild", True)))
        self.incremental_chk.setChecked(bool(cfg.get("incremental", False)))
        self.freeze_existing_chk.setChecked(bool(cfg.get("freeze_existing", False)))
        self.merge_policy_edit.setText(str(cfg.get("merge_policy_file", "")))
        self.use_deepseek_chk.setChecked(bool(cfg.get("use_deepseek", True)))
        self.series_extract_ds_chk.setChecked(bool(cfg.get("series_extract_ds", False)))
        self.author_merge_chk.setChecked(bool(cfg.get("author_merge", True)))
        self.series_missing_ds_chk.setChecked(bool(cfg.get("series_missing_ds", False)))
        self.cluster_refine_chk.setChecked(bool(cfg.get("cluster_refine", False)))
        self.circle_author_suggest_chk.setChecked(bool(cfg.get("circle_author_suggest", False)))
        _cm = cfg.get("candidate_mode", "balanced")
        idx = self.candidate_mode_combo.findData(_cm)
        if idx >= 0:
            self.candidate_mode_combo.setCurrentIndex(idx)
        else:
            self.candidate_mode_combo.setCurrentText(str(_cm))
        self.model_combo.setCurrentText(cfg.get("model", "deepseek-chat"))
        self.deepseek_max_candidates_edit.setText(str(cfg.get("deepseek_max_candidates", "-1")))
        self.timeout_edit.setText(str(cfg.get("timeout", "45")))
        self.retries_edit.setText(str(cfg.get("retries", "3")))
        self.retry_sleep_edit.setText(str(cfg.get("retry_sleep", "2")))
        self.merge_batch_edit.setText(str(cfg.get("merge_batch_size", "10")))
        self.merge_max_names_edit.setText(str(cfg.get("merge_max_names", "-1")))
        self.merge_stop_fail_edit.setText(str(cfg.get("merge_stop_fail", "5")))
        self.series_extract_max_edit.setText(str(cfg.get("series_extract_max_candidates", "-1")))
        self.series_extract_min_conf_edit.setText(str(cfg.get("series_extract_min_confidence", "70")))
        self.series_max_groups_edit.setText(str(cfg.get("series_max_groups", "-1")))
        self.cluster_max_groups_edit.setText(str(cfg.get("cluster_max_groups", "-1")))
        self.cluster_max_size_edit.setText(str(cfg.get("cluster_max_size", "12")))
        self.circle_author_max_circles_edit.setText(str(cfg.get("circle_author_max_circles", "-1")))
        self.circle_author_batch_edit.setText(str(cfg.get("circle_author_batch_size", "25")))
        self.circle_author_min_conf_edit.setText(str(cfg.get("circle_author_min_confidence", "70")))
        self.history_keep_edit.setText(str(cfg.get("history_keep", "3")))
        self.api_key_edit.setText(str(cfg.get("deepseek_api_key", "")))
        if hasattr(self, "advanced_toggle_btn"):
            expanded = bool(cfg.get("advanced_opts_expanded", False))
            self.advanced_toggle_btn.setChecked(expanded)
            self._toggle_advanced_options(expanded)
        self.last_browse_dir = str(cfg.get("last_browse_dir", self.default_output))
        try:
            x = int(cfg.get("window_x"))
            y = int(cfg.get("window_y"))
            w = int(cfg.get("window_w"))
            h = int(cfg.get("window_h"))
            if w >= 900 and h >= 600:
                target_rect = QRect(x, y, w, h)
                screen = QApplication.primaryScreen()
                if screen is not None:
                    avail = screen.availableGeometry()
                    fit_w = max(900, min(w, avail.width()))
                    fit_h = max(600, min(h, avail.height()))
                    if avail.width() < 900:
                        fit_w = avail.width()
                    if avail.height() < 600:
                        fit_h = avail.height()
                    fit_x = min(max(x, avail.left()), max(avail.left(), avail.right() - fit_w + 1))
                    fit_y = min(max(y, avail.top()), max(avail.top(), avail.bottom() - fit_h + 1))
                    if avail.intersects(target_rect):
                        self.setGeometry(QRect(fit_x, fit_y, fit_w, fit_h))
                    else:
                        self.resize(fit_w, fit_h)
                else:
                    self.setGeometry(target_rect)
            if bool(cfg.get("window_maximized", False)):
                self.showMaximized()
        except Exception:
            pass
        try:
            rx = cfg.get("review_window_x")
            ry = cfg.get("review_window_y")
            rw = cfg.get("review_window_w")
            rh = cfg.get("review_window_h")
            if rx is not None and ry is not None and rw is not None and rh is not None:
                rr = QRect(int(rx), int(ry), int(rw), int(rh))
                if rr.width() >= 900 and rr.height() >= 600:
                    self.review_window_rect = rr
            self.review_window_maximized = bool(cfg.get("review_window_maximized", False))
        except Exception:
            self.review_window_rect = None
            self.review_window_maximized = False
        try:
            h_sizes = cfg.get("main_splitter_sizes")
            if (
                isinstance(h_sizes, list)
                and len(h_sizes) >= 2
                and all(isinstance(v, (int, float)) for v in h_sizes[:2])
                and hasattr(self, "main_splitter")
            ):
                self.main_splitter.setSizes([max(100, int(h_sizes[0])), max(100, int(h_sizes[1]))])
                self._main_splitter_user_sizes = [int(self.main_splitter.sizes()[0]), int(self.main_splitter.sizes()[1])]
            v_sizes = cfg.get("left_log_err_splitter_sizes")
            if (
                isinstance(v_sizes, list)
                and len(v_sizes) >= 2
                and all(isinstance(v, (int, float)) for v in v_sizes[:2])
                and hasattr(self, "left_log_err_splitter")
            ):
                self.left_log_err_splitter.setSizes([max(80, int(v_sizes[0])), max(80, int(v_sizes[1]))])
        except Exception:
            pass
        self._sync_state()
        self._sync_tips()
        self._update_deep()







