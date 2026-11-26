"""End-to-end window tests with the REAL folder service, on tmp_path folders only (R1).

The registry is always a fake backend here: the real HKCU key is never touched.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from iconreplacer import app as app_module
from iconreplacer.catalog.registry import SourceRegistry
from iconreplacer.cli import CliOptions
from iconreplacer.core.contracts import InMemorySettingsStore
from iconreplacer.core.models import IconEntry, IconKind, IconRef, RefKind, Section, SourceInfo
from iconreplacer.services import win32_shell as w32
from iconreplacer.services.folder_icon_service import WindowsFolderIconService
from iconreplacer.services.materializer import CompositeMaterializer
from iconreplacer.services.mock_folder_service import MockFolderIconService
from iconreplacer.shell.registration import (
    COMMAND_KEY,
    VERB_KEY,
    RegistrationState,
    ShellRegistration,
)
from iconreplacer.ui.main_window import MainWindow
from iconreplacer.ui.theme import ThemeManager, ThemeMode

SHELL32 = "%SystemRoot%\\System32\\shell32.dll"


class StubResourceSource:
    """One shell32.dll icon referenced in place; renders a plain square."""

    def __init__(self) -> None:
        self._info = SourceInfo("stub-sys", "stub.dll", "stub", Section.SYSTEM)
        self.entry = IconEntry(
            "stub-sys:4", "Folder", "stub-sys", IconRef(RefKind.RESOURCE, SHELL32, 4)
        )

    @property
    def info(self) -> SourceInfo:
        return self._info

    def entries(self):
        return [self.entry]

    def render(self, entry, size):
        img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(QColor("#336699"))
        return img


class FakeBackend:
    def __init__(self) -> None:
        self.keys: dict[str, dict[str, str]] = {}

    def read_values(self, key):
        v = self.keys.get(key.lower())
        return None if v is None else dict(v)

    def write_values(self, key, values):
        self.keys.setdefault(key.lower(), {}).update(values)

    def delete_key(self, key):
        self.keys.pop(key.lower(), None)


@pytest.fixture
def work(tmp_path):
    yield tmp_path
    for root, dirs, files in os.walk(tmp_path):
        for name in dirs + files:
            w32.set_attributes(os.path.join(root, name), w32.FILE_ATTRIBUTE_NORMAL)
    shutil.rmtree(tmp_path, ignore_errors=True)


@pytest.fixture
def launcher(work):
    exe = work / "app" / "IconReplacer.exe"
    exe.parent.mkdir()
    exe.write_bytes(b"")
    return str(exe)


@pytest.fixture
def make_window(qtbot, launcher):
    def make(folders=(), backend=None):
        registry = SourceRegistry([StubResourceSource()])
        service = WindowsFolderIconService(CompositeMaterializer(registry))
        reg = ShellRegistration(backend or FakeBackend(), launcher=launcher, extra_args=())
        w = MainWindow(
            registry,
            service,
            InMemorySettingsStore({"network.allowed": True}),
            ThemeManager(QApplication.instance(), ThemeMode.LIGHT),
            [Path(f) for f in folders],
            registration=reg,
        )
        qtbot.addWidget(w)
        w.show()
        qtbot.waitExposed(w)
        return w

    return make


@pytest.fixture
def answer(monkeypatch):
    """Patch the batch confirmation; records the asked texts."""
    asked: list[str] = []

    def set_answer(yes: bool):
        def question(_parent, _title, text, *_a, **_k):
            asked.append(text)
            return QMessageBox.StandardButton.Yes if yes else QMessageBox.StandardButton.No

        monkeypatch.setattr(QMessageBox, "question", staticmethod(question))
        return asked

    return set_answer


def folders_in(base: Path, *names: str) -> list[Path]:
    out = []
    for n in names:
        p = base / n
        p.mkdir(parents=True)
        out.append(p)
    return out


def run_action(qtbot, w: MainWindow, button) -> None:
    w.last_result = None
    button.click()
    qtbot.waitUntil(lambda: w.last_result is not None and not w.runner.busy, timeout=10000)


def ini_text(folder: Path) -> str:
    data = (folder / "desktop.ini").read_bytes()
    return data.decode("utf-16") if data.startswith(b"\xff\xfe") else data.decode("mbcs")


# -- apply / undo / restore end to end ------------------------------------------------
def test_apply_undo_restore_single_folder(qtbot, work, make_window, answer):
    asked = answer(True)
    (target,) = folders_in(work, "target")
    w = make_window([target])
    w.grid.select_row(0)
    w.preview.compose.setChecked(False)

    run_action(qtbot, w, w.header.apply_btn)
    assert w.last_result.ok
    assert "IconResource=%SystemRoot%\\System32\\shell32.dll,-4" in ini_text(target)
    assert "applied to 1 folder" in w.banner_text.text()
    assert asked == []  # single folder: no confirmation
    assert w.header.apply_btn.isEnabled()

    run_action(qtbot, w, w.header.undo_btn)
    assert w.last_result.ok
    assert not (target / "desktop.ini").exists()
    assert not (target / ".iconreplacer").exists()
    assert "undone on 1 folder" in w.banner_text.text()

    w.preview.compose.setChecked(True)  # composed: a generated .ico is stored
    run_action(qtbot, w, w.header.apply_btn)
    assert list((target / ".iconreplacer").glob("icon-*.ico"))
    run_action(qtbot, w, w.header.restore_btn)
    assert w.last_result.ok
    assert not (target / "desktop.ini").exists()
    assert not (target / ".iconreplacer").exists()
    assert "restored on 1 folder" in w.banner_text.text()


def test_busy_state_disables_actions(qtbot, work, make_window, answer):
    answer(True)
    (target,) = folders_in(work, "t")
    w = make_window([target])
    w.grid.select_row(0)
    w.header.apply_btn.click()
    if w.runner.busy:  # the worker may already be done on a fast machine
        assert w.header.busy_bar.isVisibleTo(w)
        assert not w.header.apply_btn.isEnabled() and not w.header.choose_btn.isEnabled()
    qtbot.waitUntil(lambda: not w.runner.busy and w.last_result is not None)
    assert not w.header.busy_bar.isVisibleTo(w)
    assert w.header.apply_btn.isEnabled() and w.header.choose_btn.isEnabled()


def test_batch_declined_changes_nothing(qtbot, work, make_window, answer):
    asked = answer(False)
    targets = folders_in(work, "a", "b", "c")
    w = make_window(targets)
    w.grid.select_row(0)
    w.header.apply_btn.click()
    qtbot.wait(100)
    assert len(asked) == 1
    for t in targets:
        assert str(t) in asked[0]
        assert list(t.iterdir()) == []
    assert w.last_result is None and not w.runner.busy


def test_batch_confirmed_applies_all(qtbot, work, make_window, answer):
    asked = answer(True)
    targets = folders_in(work, "a", "b")
    w = make_window(targets)
    w.grid.select_row(0)
    run_action(qtbot, w, w.header.apply_btn)
    assert len(asked) == 1
    assert all((t / "desktop.ini").exists() for t in targets)
    assert "applied to 2 folders" in w.banner_text.text()


def test_failure_details_for_protected_folder(qtbot, work, make_window, answer, monkeypatch):
    answer(True)
    protected_root = work / "protected"
    monkeypatch.setenv("ProgramData", str(protected_root))  # simulate a system tree in tmp
    ok, refused = folders_in(work, "ok", "protected/inside")
    w = make_window([ok, refused])
    w.grid.select_row(0)
    run_action(qtbot, w, w.header.apply_btn)
    assert not w.last_result.ok
    assert (ok / "desktop.ini").exists()
    assert list(refused.iterdir()) == []
    assert "1 of 2 folders changed" in w.banner_text.text()
    assert w.banner_action.isVisibleTo(w) and w.banner_action.text() == "Details…"
    dlg = w.details_dialog
    assert dlg is not None and dlg.isVisible()
    assert dlg.rows() == [(str(refused), "System and program folders are protected.")]
    dlg.close()


def test_undo_without_history_reports_reason(qtbot, work, make_window):
    (target,) = folders_in(work, "fresh")
    w = make_window([target])
    run_action(qtbot, w, w.header.undo_btn)
    assert w.details_dialog.rows() == [(str(target), "Nothing to undo.")]
    w.details_dialog.close()


# -- target selection ---------------------------------------------------------------
def test_choose_folders_adds_and_deduplicates(qtbot, work, make_window, monkeypatch):
    a, b = folders_in(work, "a", "b")
    picks = iter([str(a), str(b), str(a).upper(), ""])
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", staticmethod(lambda *args, **kw: next(picks))
    )
    w = make_window()
    assert w.header.summary.text() == "No target folder"
    for _ in range(4):
        w.header.choose_btn.click()
    assert w.header.folders == (a, b)
    assert w.header.summary.text() == "2 folders"
    w.grid.select_row(0)
    assert w.header.apply_btn.isEnabled()


# -- Explorer integration ---------------------------------------------------------------
def test_registration_group_register_and_unregister(qtbot, make_window):
    backend = FakeBackend()
    w = make_window(backend=backend)
    view = w.settings_view
    assert view.registration_label.text() == "Not registered"
    assert view.register_btn.text() == "Register" and not view.unregister_btn.isEnabled()
    assert w.banner_kind() == ""
    view.register_btn.click()
    assert view.registration_label.text() == "Registered"
    assert view.register_btn.text() == "Re-register"
    assert set(backend.keys) == {VERB_KEY.lower(), COMMAND_KEY.lower()}
    view.unregister_btn.click()
    assert view.registration_label.text() == "Not registered"
    assert backend.keys == {}


def test_stale_registration_banner_fixes(qtbot, make_window, work):
    backend = FakeBackend()
    old = str(work / "old" / "IconReplacer.exe")
    backend.write_values(VERB_KEY, {"": "Replace Icon", "MUIVerb": "Replace Icon", "Icon": old})
    backend.write_values(COMMAND_KEY, {"": f'"{old}" --folder "%1"'})
    w = make_window(backend=backend)
    assert w.banner_kind() == "stale"
    assert w.banner_action.text() == "Fix Explorer integration"
    assert w.settings_view.registration_label.text().startswith("Stale")
    w.banner_action.click()
    assert w.settings_view.registration_status.state is RegistrationState.REGISTERED
    assert w.banner_kind() == ""


def test_registration_error_is_shown(qtbot, make_window):
    class Failing(FakeBackend):
        def write_values(self, key, values):
            raise PermissionError(5, "Access is denied")

    w = make_window(backend=Failing())
    w.settings_view.register_btn.click()
    assert "Access is denied" in w.settings_view.registration_label.text()


# -- wiring ---------------------------------------------------------------------------
def test_normal_wiring_is_real(qtbot, monkeypatch, launcher):
    monkeypatch.delenv(app_module.DEMO_ENV, raising=False)
    stub = StubResourceSource()
    registry = app_module.build_registry(InMemorySettingsStore(), lambda _s: [stub])
    ids = {s.info.id for s in registry.sources()}
    assert "stub-sys" in ids and "shell32.dll" in ids
    w = app_module.create_window(
        CliOptions(),
        QApplication.instance(),
        InMemorySettingsStore(),
        registry=SourceRegistry([stub]),
        registration=ShellRegistration(FakeBackend(), launcher=launcher, extra_args=()),
    )
    qtbot.addWidget(w)
    assert isinstance(w.service, WindowsFolderIconService)
    assert not w.settings_view.add_folder_btn.isVisibleTo(w.settings_view)  # no local factory
    assert app_module.extra_sources_factory(InMemorySettingsStore()) == []


def test_demo_wiring_is_simulated(qtbot, monkeypatch):
    monkeypatch.setenv(app_module.DEMO_ENV, "1")
    w = app_module.create_window(CliOptions(), QApplication.instance(), InMemorySettingsStore())
    qtbot.addWidget(w)
    assert isinstance(w.service, MockFolderIconService)
    assert w.settings_view.registration_label.text() == "Not registered"
    assert w.local_source_factory is app_module.demo_local_source
    assert len(w.registry.sources(Section.ONLINE)) > 0


def test_append_folders_deduplicates(qtbot, make_window, work):
    a, b = folders_in(work, "a", "b")
    w = make_window([a])
    app_module.append_folders(w, [Path(str(a).upper()), b])
    assert w.header.folders == (a, b)


def test_glyph_kind_is_composed_by_default(qtbot, make_window):
    w = make_window()
    w.grid.select_row(0)
    assert w.preview.entry.kind is IconKind.FULL
    assert not w.preview.compose.isChecked()
