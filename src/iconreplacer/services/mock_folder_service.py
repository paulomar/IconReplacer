"""Simulated FolderIconService for the prototype: performs NO file or registry I/O."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from iconreplacer.core.models import ActionResult, ApplyOptions, IconEntry


@dataclass(frozen=True, slots=True)
class RecordedCall:
    action: str
    folders: tuple[Path, ...]
    entry_id: str | None = None


class MockFolderIconService:
    def __init__(self) -> None:
        self.calls: list[RecordedCall] = []

    def _plural(self, folders: Sequence[Path]) -> str:
        return "1 folder" if len(folders) == 1 else f"{len(folders)} folders"

    def apply(
        self, folders: Sequence[Path], entry: IconEntry, options: ApplyOptions
    ) -> ActionResult:
        if not folders:
            return ActionResult(False, "No target folder.", simulated=True)
        self.calls.append(RecordedCall("apply", tuple(folders), entry.id))
        mode = (
            f"composed on folder base ({options.tint})"
            if options.compose_on_folder_base
            else "as-is"
        )
        return ActionResult(
            True,
            f"Simulation: '{entry.name}' would be applied {mode} to {self._plural(folders)}.",
            tuple(folders),
            simulated=True,
        )

    def undo(self, folders: Sequence[Path]) -> ActionResult:
        if not folders:
            return ActionResult(False, "No target folder.", simulated=True)
        self.calls.append(RecordedCall("undo", tuple(folders)))
        return ActionResult(
            True,
            f"Simulation: last change would be undone on {self._plural(folders)}.",
            tuple(folders),
            simulated=True,
        )

    def restore_default(self, folders: Sequence[Path]) -> ActionResult:
        if not folders:
            return ActionResult(False, "No target folder.", simulated=True)
        self.calls.append(RecordedCall("restore", tuple(folders)))
        return ActionResult(
            True,
            f"Simulation: default icon would be restored on {self._plural(folders)}.",
            tuple(folders),
            simulated=True,
        )
