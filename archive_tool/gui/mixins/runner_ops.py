from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from PyQt5.QtCore import QProcess, QTimer
from PyQt5.QtWidgets import QMessageBox

from ..log_patterns import AUTHOR_CAND_RE, DEEP_CAND_RE, DEEP_RESULT_RE, ERR_HINTS, PROGRESS_RE, SCAN_RE


def validate(self) -> list[str]:
    errors: list[str] = []
    if not self.script_path.exists():
        errors.append(f"脚本不存在: {self.script_path}")

    roots = self._collect_roots()
    if not roots:
        errors.append("至少添加一个扫描目录")
    for root in roots:
        p = Path(root)
        if not p.exists() or not p.is_dir():
            errors.append(f"扫描目录无效: {root}")

    merge_policy = self.merge_policy_edit.text().strip()
    if merge_policy and not Path(merge_policy).exists():
        errors.append(f"归并策略文件不存在: {merge_policy}")

    try:
        Path(self.output_edit.text().strip() or self.default_output).mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        errors.append(f"输出目录不可写: {exc}")

    check_rules = [
        ("超时(秒)", self.timeout_edit.text().strip(), float, lambda v: v > 0),
        ("重试次数", self.retries_edit.text().strip(), int, lambda v: v >= 0),
        ("重试等待(秒)", self.retry_sleep_edit.text().strip(), float, lambda v: v >= 0),
        ("语义复判最大候选数", self.deepseek_max_candidates_edit.text().strip(), int, lambda v: v == -1 or v >= 0),
        ("作者归并批大小", self.merge_batch_edit.text().strip(), int, lambda v: v >= 1),
        ("作者归并最大名称数", self.merge_max_names_edit.text().strip(), int, lambda v: v == -1 or v >= 0),
        ("归并连续失败终止阈值", self.merge_stop_fail_edit.text().strip(), int, lambda v: v >= 1),
        ("系列提取最大作品数", self.series_extract_max_edit.text().strip(), int, lambda v: v == -1 or v >= 0),
        ("系列提取最小置信度", self.series_extract_min_conf_edit.text().strip(), int, lambda v: 0 <= v <= 100),
        ("系列复核最大分组数", self.series_max_groups_edit.text().strip(), int, lambda v: v == -1 or v >= 0),
        ("簇复判最大分组数", self.cluster_max_groups_edit.text().strip(), int, lambda v: v == -1 or v >= 0),
        ("簇复判分组最大作品数", self.cluster_max_size_edit.text().strip(), int, lambda v: v >= 3),
        ("社团建议最大社团数", self.circle_author_max_circles_edit.text().strip(), int, lambda v: v == -1 or v >= 0),
        ("社团建议批大小", self.circle_author_batch_edit.text().strip(), int, lambda v: v >= 1),
        ("社团建议最小置信度", self.circle_author_min_conf_edit.text().strip(), int, lambda v: 0 <= v <= 100),
        ("历史保留份数", self.history_keep_edit.text().strip(), int, lambda v: v >= 0),
    ]
    for field, raw, cast, predicate in check_rules:
        try:
            if not raw or not predicate(cast(raw)):
                errors.append(f"{field} 非法")
        except Exception:
            errors.append(f"{field} 格式错误")
    return errors


def build_cmd(self) -> list[str]:
    self._sync_state()
    cmd = [
        sys.executable,
        str(self.script_path),
        *self._collect_roots(),
        "--output-dir",
        self.output_edit.text().strip() or self.default_output,
        "--state-file",
        self.state_file_path,
        "--history-keep",
        self.history_keep_edit.text().strip() or "3",
    ]
    if self.recursive_chk.isChecked():
        cmd.append("--recursive")
    if self.full_rebuild_chk.isChecked():
        cmd.append("--full-rebuild")
    if self.incremental_chk.isChecked():
        cmd.append("--incremental")
    if self.freeze_existing_chk.isChecked():
        cmd.append("--freeze-existing")

    merge_policy = self.merge_policy_edit.text().strip()
    if merge_policy:
        cmd += ["--merge-policy-file", merge_policy]

    if self.use_deepseek_chk.isChecked():
        cmd += [
            "--use-deepseek",
            "--deepseek-model",
            self.model_combo.currentText(),
            "--deepseek-candidate-mode",
            self.candidate_mode_combo.currentData() or "balanced",
            "--deepseek-max-candidates",
            self.deepseek_max_candidates_edit.text().strip() or "-1",
            "--deepseek-timeout",
            self.timeout_edit.text().strip() or "45",
            "--deepseek-retries",
            self.retries_edit.text().strip() or "3",
            "--deepseek-retry-sleep",
            self.retry_sleep_edit.text().strip() or "2",
        ]
        if self.series_extract_ds_chk.isChecked():
            cmd += [
                "--deepseek-series-extract",
                "--deepseek-series-extract-max-candidates",
                self.series_extract_max_edit.text().strip() or "-1",
                "--deepseek-series-extract-min-confidence",
                self.series_extract_min_conf_edit.text().strip() or "70",
            ]
        if self.author_merge_chk.isChecked():
            cmd += [
                "--deepseek-author-merge",
                "--deepseek-author-merge-max-names",
                self.merge_max_names_edit.text().strip() or "-1",
                "--deepseek-author-merge-batch-size",
                self.merge_batch_edit.text().strip() or "10",
                "--deepseek-author-merge-stop-after-fail-batches",
                self.merge_stop_fail_edit.text().strip() or "5",
            ]
        if self.series_missing_ds_chk.isChecked():
            cmd += [
                "--deepseek-series-missing",
                "--deepseek-series-max-groups",
                self.series_max_groups_edit.text().strip() or "-1",
            ]
        if self.cluster_refine_chk.isChecked():
            cmd += [
                "--deepseek-cluster-refine",
                "--deepseek-cluster-max-groups",
                self.cluster_max_groups_edit.text().strip() or "-1",
                "--deepseek-cluster-max-size",
                self.cluster_max_size_edit.text().strip() or "12",
            ]
        if self.circle_author_suggest_chk.isChecked():
            cmd += [
                "--deepseek-circle-author-suggest",
                "--deepseek-circle-author-max-circles",
                self.circle_author_max_circles_edit.text().strip() or "-1",
                "--deepseek-circle-author-batch-size",
                self.circle_author_batch_edit.text().strip() or "25",
                "--deepseek-circle-author-min-confidence",
                self.circle_author_min_conf_edit.text().strip() or "70",
            ]
    return cmd


def start(self) -> None:
    if self.proc and self.proc.state() != QProcess.NotRunning:
        QMessageBox.warning(self, "运行中", "已有任务在运行")
        return

    errors = validate(self)
    if errors:
        QMessageBox.critical(self, "启动前检查失败", "\n".join(f"- {x}" for x in errors))
        return

    cmd = build_cmd(self)
    self._save_config(True)
    self.stage_progress = {"Parse": 0.0, "AuthorMerge": 0.0, "DeepSeek": 0.0}
    self.stop_requested = False
    self._stream_buffer = ""
    self._log_lines = []
    self._progress_lines = {}
    self._last_rendered_log = ""
    self.log_text.clear()
    self._append_log(f"\n[GUI] 启动命令:\n{' '.join(cmd)}\n\n")

    self.stage_weights = {
        "Parse": 0.6,
        "AuthorMerge": 0.2 if (self.use_deepseek_chk.isChecked() and self.author_merge_chk.isChecked()) else 0.0,
        "DeepSeek": 0.2 if self.use_deepseek_chk.isChecked() else 0.0,
    }
    if not self.use_deepseek_chk.isChecked():
        self.stage_weights["Parse"] = 1.0

    self.progress.setStyleSheet("")
    self.progress.setFormat("%p%")
    self.progress.setValue(0)
    self.lbl_parse.setText("0%")
    self.lbl_author.setText("-")
    self.lbl_deep.setText("-")
    if hasattr(self, "series_max_groups_value"):
        self.series_max_groups_value.setText("自动（待检测）")
    self._clear_errors()

    self.run_started_at = time.time()
    self.timer.start(1000)
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    api_key = self.api_key_edit.text().strip()
    if api_key:
        env["DEEPSEEK_API_KEY"] = api_key
    elif self.use_deepseek_chk.isChecked() and not env.get("DEEPSEEK_API_KEY", "").strip():
        self._append_err("[WARN] 未填写 API Key 且环境变量为空，DeepSeek 将被跳过")

    self.proc = QProcess(self)
    self.proc.setWorkingDirectory(str(self.base_dir))
    self.proc.setProcessChannelMode(QProcess.MergedChannels)
    qenv = self.proc.processEnvironment()
    for k, v in env.items():
        qenv.insert(k, v)
    self.proc.setProcessEnvironment(qenv)
    self.proc.readyReadStandardOutput.connect(self._on_out)
    self.proc.finished.connect(self._on_done)
    self.proc.start(cmd[0], cmd[1:])
    if not self.proc.waitForStarted(5000):
        QMessageBox.critical(self, "启动失败", "无法启动子进程")
        self.timer.stop()
        return
    self.btn_run.setEnabled(False)
    self.btn_stop.setEnabled(True)


def on_out(self) -> None:
    if not self.proc:
        return
    data = bytes(self.proc.readAllStandardOutput()).decode("utf-8", errors="replace")
    if not data:
        return
    self._stream_buffer += data.replace("\r", "\n")
    lines = self._stream_buffer.split("\n")
    self._stream_buffer = lines.pop() if lines else ""

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if any(k in line for k in ERR_HINTS):
            self._append_err(line)

        m = SCAN_RE.search(line)
        if m:
            self.lbl_entries.setText(m.group(1))
        m = AUTHOR_CAND_RE.search(line)
        if m:
            self.lbl_author.setText(f"候选={m.group(1)}")
        m = DEEP_CAND_RE.search(line)
        if m:
            self.lbl_deep.setText(f"候选={m.group(1)}")
        m = DEEP_RESULT_RE.search(line)
        if m:
            self.lbl_deep.setText(f"已复判={m.group(1)} 失败={m.group(2)}")
            self.stage_progress["DeepSeek"] = 1.0

        m = PROGRESS_RE.search(line)
        if m:
            raw_stage, cur, total = m.group(1), int(m.group(2)), max(1, int(m.group(3)))
            stage_map = {
                "Parse": "Parse",
                "解析": "Parse",
                "AuthorMerge": "AuthorMerge",
                "作者归并": "AuthorMerge",
                "DeepSeek": "DeepSeek",
                "SeriesMissing][DeepSeek": "SeriesMissing",
            }
            stage = stage_map.get(raw_stage, raw_stage)
            ratio = cur / total
            if stage in self.stage_progress:
                self.stage_progress[stage] = ratio
            if stage == "Parse":
                self.lbl_parse.setText(f"{ratio * 100:.1f}% ({cur}/{total})")
            elif stage == "AuthorMerge":
                self.lbl_author.setText(f"{ratio * 100:.1f}% ({cur}/{total})")
            elif stage == "DeepSeek":
                self.lbl_deep.setText(f"{ratio * 100:.1f}% ({cur}/{total})")
            elif stage == "SeriesMissing":
                self.lbl_deep.setText(f"系列缺失复核 {ratio * 100:.1f}% ({cur}/{total})")
            self._set_live_progress(stage, line)
        else:
            self._append_log(line + "\n")

        denom = max(1e-6, sum(self.stage_weights.values()))
        progress = (
            self.stage_progress["Parse"] * self.stage_weights["Parse"]
            + self.stage_progress["AuthorMerge"] * self.stage_weights["AuthorMerge"]
            + self.stage_progress["DeepSeek"] * self.stage_weights["DeepSeek"]
        ) / denom
        self.progress.setValue(max(0, min(1000, int(progress * 1000))))


def on_done(self, code: int, _status: QProcess.ExitStatus) -> None:
    if self._stream_buffer.strip():
        self._append_log(self._stream_buffer.strip() + "\n")
        self._stream_buffer = ""
    self._flush_live_progress()
    self.timer.stop()

    if code == 0:
        self.progress.setValue(1000)
        self.progress.setFormat("100%")
    else:
        self.progress.setStyleSheet("QProgressBar::chunk { background-color: #d9534f; }")
        self.progress.setFormat(f"失败 (exit={code})")
        if self.progress.value() >= 1000:
            self.progress.setValue(999)

    self._append_log(f"\n[GUI] 任务结束, exit_code={code}\n")
    self.btn_run.setEnabled(True)
    self.btn_stop.setEnabled(False)
    self.btn_stop.setText("停止")
    self.stop_requested = False
    self._update_result_buttons()
    self._load_output_stats()


def stop(self) -> None:
    if not self.proc or self.proc.state() == QProcess.NotRunning:
        return
    if self.stop_requested:
        self.proc.kill()
        self._append_log("[GUI] 已执行强制终止\n")
        return
    self.stop_requested = True
    self.btn_stop.setText("强制停止")
    self.proc.terminate()
    self._append_log("[GUI] 已发送停止信号\n")
    QTimer.singleShot(1500, self._force_kill_if_running)


def force_kill_if_running(self) -> None:
    if self.proc and self.proc.state() != QProcess.NotRunning:
        self.proc.kill()
        self._append_log("[GUI] terminate 未生效，已执行强制终止\n")


def tick_elapsed(self) -> None:
    self.lbl_elapsed.setText(f"{int(time.time() - (self.run_started_at or time.time()))}s")





