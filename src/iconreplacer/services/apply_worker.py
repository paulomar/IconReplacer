"""Run folder actions off the GUI thread and deliver results back on it."""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from iconreplacer.core.models import ActionResult

log = logging.getLogger(__name__)


class _Relay(QObject):
    done = Signal(str, object)  # action name, ActionResult


class _Job(QRunnable):
    def __init__(self, action: str, fn: Callable[[], ActionResult], relay: _Relay) -> None:
        super().__init__()
        self._action = action
        self._fn = fn
        self._relay = relay

    def run(self) -> None:
        try:
            result = self._fn()
        except Exception as exc:  # services are pluggable: never lose the result
            log.exception("folder action %s failed", self._action)
            result = ActionResult(False, str(exc) or type(exc).__name__)
        self._relay.done.emit(self._action, result)


class ActionRunner(QObject):
    """Serializes folder actions on one worker thread.

    ``finished(action, result)`` is emitted on the thread that owns the runner (the GUI thread),
    because the relay object lives there and the signal crosses threads as a queued connection.
    """

    started = Signal(str)
    finished = Signal(str, object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._relay = _Relay(self)
        self._relay.done.connect(self._on_done)
        self._pending = 0

    @property
    def busy(self) -> bool:
        return self._pending > 0

    def submit(self, action: str, fn: Callable[[], ActionResult]) -> None:
        self._pending += 1
        self.started.emit(action)
        self._pool.start(_Job(action, fn, self._relay))

    def wait(self, msecs: int = -1) -> bool:
        return self._pool.waitForDone(msecs)

    def _on_done(self, action: str, result: ActionResult) -> None:
        self._pending = max(0, self._pending - 1)
        self.finished.emit(action, result)
