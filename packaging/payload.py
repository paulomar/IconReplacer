"""Payload rules shared by the PyInstaller spec and the tests (no PyInstaller import)."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

SKIP_SUFFIXES = {".py", ".pyc", ".pyo"}
SKIP_DIRS = {"__pycache__"}

# Qt modules the application does not use (QtNetwork is kept: local IPC and downloads).
EXCLUDED_QT_MODULES = [
    "Qt3DCore", "Qt3DRender", "Qt3DInput", "Qt3DLogic", "Qt3DAnimation", "Qt3DExtras",
    "QtBluetooth", "QtCharts", "QtConcurrent", "QtDataVisualization", "QtDBus", "QtDesigner",
    "QtHelp", "QtMultimedia", "QtMultimediaWidgets", "QtNfc", "QtOpenGL", "QtOpenGLWidgets",
    "QtPdf", "QtPdfWidgets", "QtPositioning", "QtPrintSupport", "QtQml", "QtQuick",
    "QtQuickControls2", "QtQuickWidgets", "QtRemoteObjects", "QtScxml", "QtSensors",
    "QtSerialPort", "QtSql", "QtStateMachine", "QtTest", "QtTextToSpeech", "QtUiTools",
    "QtWebChannel", "QtWebEngineCore", "QtWebEngineWidgets", "QtWebSockets", "QtXml",
]  # fmt: skip

# Binary name fragments (lower case) dropped from the bundle.
EXCLUDED_BINARY_FRAGMENTS = (
    "opengl32sw", "d3dcompiler", "qt6pdf", "qt6qml", "qt6quick", "qt6opengl", "qt6virtualkeyboard",
    "qt6dbus", "qt6printsupport", "qt6multimedia", "ffmpeg", "avcodec", "avformat", "avutil",
    "swresample", "swscale",
)  # fmt: skip

KEPT_IMAGE_PLUGINS = {"qico", "qsvg", "qicns", "qwebp", "qjpeg"}
KEPT_PLUGIN_GROUPS = {
    "platforms": {"qwindows"},
    "imageformats": KEPT_IMAGE_PLUGINS,
    "styles": None,  # None: keep everything in the group
    "iconengines": None,
    "tls": None,
    "networkinformation": None,
}


def collect_package_data(
    package_dir: Path, dest_root: str = "iconreplacer"
) -> list[tuple[str, str]]:
    """Every non-Python file under ``package_dir`` as ``(source, dest_dir)`` pairs."""
    pairs: list[tuple[str, str]] = []
    for path in sorted(package_dir.rglob("*")):
        rel = path.relative_to(package_dir)
        if not path.is_file() or SKIP_DIRS.intersection(rel.parts):
            continue
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        dest = PurePosixPath(dest_root, *rel.parts[:-1])
        pairs.append((str(path), str(dest)))
    return pairs


def keep_toc_entry(dest_name: str) -> bool:
    """False for binaries/data that should be dropped to keep the bundle small."""
    norm = dest_name.replace("\\", "/")
    low = norm.lower()
    if any(fragment in low.rsplit("/", 1)[-1] for fragment in EXCLUDED_BINARY_FRAGMENTS):
        return False
    if "/translations/" in low and "pyside6" in low:
        return False
    marker = "/plugins/"
    if marker in low and "pyside6" in low:
        parts = norm[low.index(marker) + len(marker) :].split("/")
        group, name = parts[0].lower(), parts[-1]
        if group not in KEPT_PLUGIN_GROUPS:
            return False
        allowed = KEPT_PLUGIN_GROUPS[group]
        if allowed is not None and len(parts) > 1:
            return name.lower().split(".")[0] in allowed
    return True
