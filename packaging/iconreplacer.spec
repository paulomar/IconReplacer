# PyInstaller spec: onedir, windowed IconReplacer.exe + console iconreplacer-cli.exe.
# Run through tools/build_release.py (it prepares build/app.ico and the version files first).
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

HERE = Path(SPECPATH)  # noqa: F821
ROOT = HERE.parent
BUILD = ROOT / "build"
sys.path.insert(0, str(HERE))

from payload import (  # noqa: E402
    EXCLUDED_QT_MODULES,
    collect_package_data,
    keep_toc_entry,
)

datas = collect_package_data(ROOT / "src" / "iconreplacer")
hidden = collect_submodules("iconreplacer") + ["PySide6.QtSvg", "PySide6.QtNetwork"]
excludes = [f"PySide6.{m}" for m in EXCLUDED_QT_MODULES] + ["tkinter", "unittest", "pydoc"]


def analysis(script):
    return Analysis(  # noqa: F821
        [str(HERE / script)],
        pathex=[str(ROOT / "src")],
        datas=datas,
        hiddenimports=hidden,
        excludes=excludes,
        noarchive=False,
    )


gui = analysis("entry_gui.py")
cli = analysis("entry_cli.py")
MERGE((gui, "entry_gui", "IconReplacer"), (cli, "entry_cli", "iconreplacer-cli"))  # noqa: F821

for a in (gui, cli):
    a.binaries = [e for e in a.binaries if keep_toc_entry(e[0])]
    a.datas = [e for e in a.datas if keep_toc_entry(e[0])]

icon = str(BUILD / "app.ico")


def make_exe(a, name, windowed, version_file):
    return EXE(  # noqa: F821
        PYZ(a.pure),  # noqa: F821
        a.scripts,
        [],
        exclude_binaries=True,
        name=name,
        console=not windowed,
        icon=icon,
        version=str(BUILD / version_file),
        upx=False,
    )


exe_gui = make_exe(gui, "IconReplacer", True, "version_info_gui.txt")
exe_cli = make_exe(cli, "iconreplacer-cli", False, "version_info_cli.txt")

COLLECT(  # noqa: F821
    exe_gui,
    gui.binaries,
    gui.datas,
    exe_cli,
    cli.binaries,
    cli.datas,
    upx=False,
    name="IconReplacer",
)
