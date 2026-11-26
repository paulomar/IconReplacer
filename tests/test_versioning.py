import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import bump_version  # noqa: E402
from iconreplacer import version  # noqa: E402
from iconreplacer.cli import parse_args  # noqa: E402

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+\.\d+$")


def test_version_format_and_single_source():
    assert VERSION_RE.match(version.__version__)
    assert version.__version__ == ".".join(map(str, version.VERSION))
    assert ".".join(map(str, version.VERSION[:3])) == version.SHORT_VERSION


def test_build_always_increments():
    assert bump_version.bump((0, 1, 0, 1), "build") == (0, 1, 0, 2)
    assert bump_version.bump((0, 1, 0, 1), "patch") == (0, 1, 1, 2)
    assert bump_version.bump((0, 1, 3, 4), "major") == (1, 0, 0, 5)


def test_build_does_not_reset_on_minor_bump():
    assert bump_version.bump((0, 1, 2, 5), "minor") == (0, 2, 0, 6)


def test_unknown_part_rejected():
    with pytest.raises(ValueError):
        bump_version.bump((0, 1, 0, 1), "nope")


def test_rewrite_roundtrip(tmp_path):
    src = (ROOT / "src" / "iconreplacer" / "version.py").read_text(encoding="utf-8")
    f = tmp_path / "version.py"
    f.write_text(src, encoding="utf-8")
    current = bump_version.read_version(src)
    assert bump_version.main(["minor", "--file", str(f)]) == 0
    text = f.read_text(encoding="utf-8")
    expected = bump_version.bump(current, "minor")
    assert bump_version.read_version(text) == expected
    assert f'__version__ = "{".".join(map(str, expected))}"' in text


def test_cli_folders_repeatable_and_deduplicated():
    opts = parse_args(["--folder", r"C:\A", "--folder", r"C:\B", "--folder", r"c:\a"])
    assert [str(p) for p in opts.folders] == [r"C:\A", r"C:\B"]


def test_cli_version_prints_and_exits_without_window():
    result = subprocess.run(
        [sys.executable, "-m", "iconreplacer", "--version"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == f"IconReplacer {version.__version__}"


def test_version_flag_does_not_import_qt():
    code = (
        "import sys\n"
        "from iconreplacer.cli import parse_args\n"
        "try:\n    parse_args(['--version'])\nexcept SystemExit:\n    pass\n"
        "print(any(m.startswith('PySide6') for m in sys.modules))"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    assert out.stdout.strip().endswith("False")
