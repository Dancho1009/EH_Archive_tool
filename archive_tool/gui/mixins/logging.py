from __future__ import annotations

from pathlib import Path

from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication, QLineEdit, QToolTip


class GuiLoggingMixin:
    def _append_log(self, text: str) -> None:
        for seg in text.replace("\r", "\n").split("\n"):
            seg = seg.strip()
            if seg:
                self._log_lines.append(seg)
        if len(self._log_lines) > self.max_log_lines:
            self._log_lines = self._log_lines[-self.max_log_lines :]
        self._render_log()

    def _append_err(self, line: str) -> None:
        line = line.strip()
        if not line or line in self.error_seen:
            return
        self.error_seen.add(line)
        self.error_text.appendPlainText(line)
        self.error_count += 1
        self.lbl_failed.setText(str(self.error_count))

    def _clear_errors(self) -> None:
        self.error_text.clear()
        self.error_seen.clear()
        self.error_count = 0
        self.lbl_failed.setText("0")

    def _set_live_progress(self, stage: str, line: str) -> None:
        self._progress_lines[stage] = line.strip()
        self._render_log()

    def _flush_live_progress(self) -> None:
        if not self._progress_lines:
            return
        self._log_lines.extend(
            [
                self._progress_lines[k]
                for k in ["Parse", "AuthorMerge", "DeepSeek", "SeriesMissing"]
                if k in self._progress_lines
            ]
        )
        if len(self._log_lines) > self.max_log_lines:
            self._log_lines = self._log_lines[-self.max_log_lines :]
        self._progress_lines.clear()
        self._render_log()

    def _render_log(self) -> None:
        progress_order = ["Parse", "AuthorMerge", "DeepSeek", "SeriesMissing"]
        lines = list(self._log_lines)
        lines.extend([self._progress_lines[k] for k in progress_order if k in self._progress_lines])
        text = "\n".join(lines)
        if text == self._last_rendered_log:
            return
        self.log_text.setPlainText(text)
        self.log_text.moveCursor(self.log_text.textCursor().End)
        self._last_rendered_log = text

    def _copy_text(self, text: str) -> None:
        QApplication.clipboard().setText(text)
        QToolTip.showText(self.mapToGlobal(self.rect().center()), "已复制", self)

    def _toggle_api_key_visibility(self) -> None:
        self.api_key_visible = not self.api_key_visible
        self.api_key_edit.setEchoMode(QLineEdit.Normal if self.api_key_visible else QLineEdit.Password)
        self.btn_toggle_api.setText("隐藏" if self.api_key_visible else "显示")

    def _sync_tips(self) -> None:
        self.output_edit.setToolTip(self.output_edit.text())

    def _sync_state(self) -> None:
        output_dir = Path(self.output_edit.text().strip() or self.default_output)
        self.state_file_path = str((output_dir / "archive_state.json").resolve())
        self.freeze_existing_chk.setEnabled(self.incremental_chk.isChecked())

    def _on_output_changed(self) -> None:
        self._sync_state()
        self._sync_tips()
        self._update_result_buttons()
        self._load_output_stats()

    def _on_mode_toggle(self, checked: bool) -> None:
        sender = self.sender()
        if sender is self.full_rebuild_chk and checked:
            self.incremental_chk.blockSignals(True)
            self.incremental_chk.setChecked(False)
            self.incremental_chk.blockSignals(False)
            self.freeze_existing_chk.setChecked(False)
        elif sender is self.incremental_chk and checked:
            self.full_rebuild_chk.blockSignals(True)
            self.full_rebuild_chk.setChecked(False)
            self.full_rebuild_chk.blockSignals(False)
        self.freeze_existing_chk.setEnabled(self.incremental_chk.isChecked())

    def _update_deep(self) -> None:
        enabled = self.use_deepseek_chk.isChecked()
        if hasattr(self, "advanced_group"):
            self.advanced_group.setEnabled(enabled)

        for w in [
            self.api_key_edit,
            self.btn_toggle_api,
            self.model_combo,
            self.candidate_mode_combo,
            self.deepseek_max_candidates_edit,
            self.timeout_edit,
            self.retries_edit,
            self.retry_sleep_edit,
        ]:
            w.setEnabled(enabled)
        self.author_merge_chk.setEnabled(enabled)
        self.series_extract_ds_chk.setEnabled(enabled)
        self.series_missing_ds_chk.setEnabled(enabled)
        self.cluster_refine_chk.setEnabled(enabled)
        self.circle_author_suggest_chk.setEnabled(enabled)

        merge_enabled = enabled and self.author_merge_chk.isChecked()
        self.merge_batch_edit.setEnabled(merge_enabled)
        self.merge_max_names_edit.setEnabled(merge_enabled)
        self.merge_stop_fail_edit.setEnabled(merge_enabled)
        self.series_extract_max_edit.setEnabled(enabled and self.series_extract_ds_chk.isChecked())
        self.series_extract_min_conf_edit.setEnabled(enabled and self.series_extract_ds_chk.isChecked())
        self.series_max_groups_edit.setEnabled(enabled and self.series_missing_ds_chk.isChecked())
        self.cluster_max_groups_edit.setEnabled(enabled and self.cluster_refine_chk.isChecked())
        self.cluster_max_size_edit.setEnabled(enabled and self.cluster_refine_chk.isChecked())
        self.circle_author_max_circles_edit.setEnabled(enabled and self.circle_author_suggest_chk.isChecked())
        self.circle_author_batch_edit.setEnabled(enabled and self.circle_author_suggest_chk.isChecked())
        self.circle_author_min_conf_edit.setEnabled(enabled and self.circle_author_suggest_chk.isChecked())

    def _apply_log_fonts(self) -> None:
        self.log_text.setFont(QFont("Consolas", 10))
        self.error_text.setFont(QFont("Consolas", 10))









