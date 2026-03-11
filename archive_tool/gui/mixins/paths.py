from __future__ import annotations

from pathlib import Path

from PyQt5.QtWidgets import QFileDialog


class GuiPathMixin:
    def _collect_roots(self) -> list[str]:
        return [self.roots_list.item(i).text() for i in range(self.roots_list.count())]

    def _add_root(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择扫描目录", self.last_browse_dir)
        if not directory:
            return
        self.last_browse_dir = directory
        if directory not in set(self._collect_roots()):
            self.roots_list.addItem(directory)
        self._save_config(True)

    def _remove_root(self) -> None:
        idx = self.roots_list.currentRow()
        if idx >= 0:
            self.roots_list.takeItem(idx)
            self._save_config(True)

    def _up_root(self) -> None:
        idx = self.roots_list.currentRow()
        if idx <= 0:
            return
        item = self.roots_list.takeItem(idx)
        self.roots_list.insertItem(idx - 1, item)
        self.roots_list.setCurrentRow(idx - 1)
        self._save_config(True)

    def _down_root(self) -> None:
        idx = self.roots_list.currentRow()
        if idx < 0 or idx >= self.roots_list.count() - 1:
            return
        item = self.roots_list.takeItem(idx)
        self.roots_list.insertItem(idx + 1, item)
        self.roots_list.setCurrentRow(idx + 1)
        self._save_config(True)

    def _dedupe_roots(self) -> None:
        seen: set[str] = set()
        ordered: list[str] = []
        for path in self._collect_roots():
            if path in seen:
                continue
            seen.add(path)
            ordered.append(path)
        self.roots_list.clear()
        for path in ordered:
            self.roots_list.addItem(path)
        self._save_config(True)

    def _clear_roots(self) -> None:
        self.roots_list.clear()
        self._save_config(True)

    def _choose_output(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择输出目录", self.last_browse_dir)
        if not directory:
            return
        self.last_browse_dir = directory
        self.output_edit.setText(directory)
        self._save_config(True)

    def _choose_merge_policy(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择归并策略文件",
            self.last_browse_dir,
            "JSON Files (*.json);;All Files (*)",
        )
        if not file_path:
            return
        self.merge_policy_edit.setText(file_path)
        self.last_browse_dir = str(Path(file_path).resolve().parent)
        self._save_config(True)
