from __future__ import annotations

from . import runner_ops


class GuiRunnerMixin:
    def _validate(self) -> list[str]:
        return runner_ops.validate(self)

    def _build_cmd(self) -> list[str]:
        return runner_ops.build_cmd(self)

    def _start(self) -> None:
        runner_ops.start(self)

    def _on_out(self) -> None:
        runner_ops.on_out(self)

    def _on_done(self, code: int, status) -> None:
        runner_ops.on_done(self, code, status)

    def _stop(self) -> None:
        runner_ops.stop(self)

    def _force_kill_if_running(self) -> None:
        runner_ops.force_kill_if_running(self)

    def _tick_elapsed(self) -> None:
        runner_ops.tick_elapsed(self)
