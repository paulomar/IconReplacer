# Design

## Decisions

- **onedir, not onefile.** Onefile unpacks to a temp folder on every launch (slow from the
  context menu, AV-prone) and breaks "data next to the exe". onedir starts fast.
- **Console companion, not AttachConsole.** A windowed exe has `sys.stdout = None` and cmd
  does not wait for GUI programs, so output is racy and pipe capture is unreliable. A second
  console EXE in the same `COLLECT` shares `_internal/` (a few hundred KB extra) and gives
  reliable, scriptable output. The companion entry point patches
  `shell.registration.default_launcher` to the sibling `IconReplacer.exe`, so the registered
  verb never opens a console window. Application code stays untouched.
- **Generic data collection.** The spec walks `src/iconreplacer/` and bundles every non-`.py`
  / non-`.pyc` file to the same relative folder, so other changes can add data files freely.
  Hidden imports come from `collect_submodules("iconreplacer")`.
- **Size.** Qt modules unused by the app (QtNetwork, QtQml, QtQuick, QtPdf, QtOpenGL, QtDBus,
  Qt3D, QtWebEngine, QtMultimedia, ...) and plugins other than platform/styles/imageformats/
  iconengines are excluded; the FFmpeg/ opengl32sw / translations are dropped from binaries.
- **Version info and icon at build time**: `packaging/make_version_info.py` renders a
  PyInstaller `VSVersionInfo` text from `version.py`; `packaging/make_app_icon.py` paints a
  folder with a sparkle using QPainter (offscreen) and writes the ICO with `converter.build_ico`.
- **Pipeline** (`tools/build_release.py`): clean `build/` and `dist/`, compile `.qm`, generate
  icon and version file, run PyInstaller via `python -m PyInstaller`, smoke test, stage the
  portable folder (LICENSE, notices, README-PORTABLE), zip, write SHA-256.
- **Portable mode** needs no code change: `core.paths.app_dir()` already returns the exe
  folder when frozen.

## Risks

- Unsigned executables can trigger SmartScreen/AV heuristics (documented in README-PORTABLE).
- The window icon is set by the application, not the exe resource; the exe icon only affects
  Explorer and the taskbar entry.
