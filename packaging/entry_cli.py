"""Frozen console companion (iconreplacer-cli.exe): same code, console subsystem.

The Explorer verb must always launch the windowed ``IconReplacer.exe``, so the registration
launcher is pointed at the sibling GUI executable.
"""

import sys
from pathlib import Path

GUI_EXE = "IconReplacer.exe"


def gui_launcher() -> tuple[str, tuple[str, ...]]:
    return str(Path(sys.executable).resolve().with_name(GUI_EXE)), ()


def run() -> int:
    from iconreplacer.__main__ import main
    from iconreplacer.shell import registration

    if getattr(sys, "frozen", False):
        registration.default_launcher = gui_launcher
    return main()


if __name__ == "__main__":
    sys.exit(run())
