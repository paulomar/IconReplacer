"""Build the portable release zip.

Usage:
    uv run python tools/build_release.py            # full build
    uv run python tools/build_release.py --keep     # keep build/ (skip the initial clean)

Steps: clean -> compile translations -> app icon + version info -> PyInstaller -> smoke test
-> stage portable folder -> zip -> SHA-256. Exits non-zero on any failure.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "packaging"))

from iconreplacer.version import FULL_VERSION  # noqa: E402

BUILD = ROOT / "build"
DIST = ROOT / "dist"
PYI_DIST = BUILD / "pyi-dist"
PYI_WORK = BUILD / "pyi-work"
SPEC = ROOT / "packaging" / "iconreplacer.spec"
GUI_EXE = "IconReplacer.exe"
CLI_EXE = "iconreplacer-cli.exe"
EXTRA_FILES = {
    "LICENSE": ROOT / "LICENSE",
    "THIRD_PARTY_NOTICES.md": ROOT / "THIRD_PARTY_NOTICES.md",
    "README-PORTABLE.txt": ROOT / "packaging" / "README-PORTABLE.txt",
}


class BuildError(RuntimeError):
    pass


def folder_name(version: str = FULL_VERSION) -> str:
    return f"IconReplacer-{version}-win64"


def run(cmd: list[str], **kwargs) -> None:
    print("+", " ".join(str(c) for c in cmd), flush=True)
    env = {**os.environ, "PYTHONUTF8": "1"}
    if subprocess.call(cmd, cwd=ROOT, env=env, **kwargs) != 0:
        raise BuildError(f"command failed: {cmd[0]} {cmd[1] if len(cmd) > 1 else ''}")


def clean() -> None:
    for path in (BUILD, DIST):
        shutil.rmtree(path, ignore_errors=True)
    BUILD.mkdir(parents=True)
    DIST.mkdir(parents=True)


def prepare_assets() -> None:
    import make_app_icon
    import make_version_info

    make_app_icon.build(BUILD / "app.ico")
    make_version_info.write(BUILD / "version_info_gui.txt", GUI_EXE)
    make_version_info.write(
        BUILD / "version_info_cli.txt", CLI_EXE, "IconReplacer (console companion)"
    )


def smoke_test(folder: Path, version: str = FULL_VERSION) -> str:
    """Run ``--version`` (and ``--status``) from the built folder; raise on mismatch."""
    env = {k: v for k, v in os.environ.items() if k != "ICONREPLACER_HOME"}
    cli = folder / CLI_EXE
    proc = subprocess.run(
        [str(cli), "--version"], capture_output=True, text=True, timeout=120, env=env
    )
    out = proc.stdout.strip()
    expected = f"IconReplacer {version}"
    if proc.returncode != 0 or out != expected:
        raise BuildError(
            f"smoke test failed: got {out!r} (rc={proc.returncode}), want {expected!r}"
        )
    gui = subprocess.run([str(folder / GUI_EXE), "--version"], timeout=120, env=env)
    if gui.returncode != 0:
        raise BuildError(f"{GUI_EXE} --version exited with {gui.returncode}")
    status = subprocess.run(
        [str(cli), "--status"], capture_output=True, text=True, timeout=120, env=env
    )
    if status.returncode not in (0, 1) or not status.stdout.strip():
        raise BuildError(f"--status smoke test failed: {status.stdout!r} {status.stderr!r}")
    print(f"smoke: {out!r}; --status: {status.stdout.strip()!r}")
    return out


def stage(built: Path, target_parent: Path, version: str = FULL_VERSION) -> Path:
    """Copy the PyInstaller folder to ``<name>/`` and add the license/notice/readme files."""
    target = target_parent / folder_name(version)
    shutil.rmtree(target, ignore_errors=True)
    shutil.copytree(built, target)
    for name, src in EXTRA_FILES.items():
        if not src.is_file():
            raise BuildError(f"missing release file: {src}")
        shutil.copy2(src, target / name)
    return target


def make_zip(folder: Path, zip_path: Path) -> Path:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                zf.write(path, Path(folder.name) / path.relative_to(folder))
    return zip_path


def write_checksum(zip_path: Path) -> Path:
    digest = hashlib.sha256()
    with zip_path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    out = zip_path.with_name(zip_path.name + ".sha256")
    out.write_text(f"{digest.hexdigest()} *{zip_path.name}\n", encoding="utf-8")
    return out


def build(keep: bool = False) -> Path:
    started = time.perf_counter()
    if keep:
        shutil.rmtree(PYI_DIST, ignore_errors=True)
        BUILD.mkdir(exist_ok=True)
        DIST.mkdir(exist_ok=True)
    else:
        clean()
    run([sys.executable, str(ROOT / "tools" / "update_translations.py"), "--release"])
    prepare_assets()
    run(
        [
            sys.executable, "-m", "PyInstaller", str(SPEC), "--noconfirm", "--clean",
            "--distpath", str(PYI_DIST), "--workpath", str(PYI_WORK),
        ]
    )  # fmt: skip
    built = PYI_DIST / "IconReplacer"
    smoke_test(built)
    staged = stage(built, BUILD / "stage")
    zip_path = make_zip(staged, DIST / f"{folder_name()}.zip")
    checksum = write_checksum(zip_path)
    size = zip_path.stat().st_size / 1_048_576
    print(f"built {zip_path} ({size:.1f} MiB) in {time.perf_counter() - started:.0f}s")
    print(f"checksum {checksum.read_text(encoding='utf-8').strip()}")
    return zip_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--keep", action="store_true", help="do not wipe build/ and dist/ first")
    args = parser.parse_args(argv)
    try:
        build(keep=args.keep)
    except (BuildError, subprocess.SubprocessError, OSError) as exc:
        print(f"BUILD FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
