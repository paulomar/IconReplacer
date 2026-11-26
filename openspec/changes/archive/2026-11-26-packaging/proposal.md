# Proposal

## Why

IconReplacer is only runnable from a development checkout. Users need a single
portable download they can unzip and run without Python, an installer or admin rights,
and the Explorer context-menu entry must launch quickly from that folder.

## What Changes

- Add a PyInstaller **onedir** build (windowed `IconReplacer.exe`) plus a small console
  companion `iconreplacer-cli.exe` for `--version/--status/--register` output.
- Generate a Windows VERSIONINFO resource and an original application icon at build time.
- Bundle every non-`.py` package data file generically (JSON catalogs, compiled `.qm`).
- Trim unused Qt modules and plugins to keep the archive small.
- Add `tools/build_release.py` (clean build, translations, icon, version info, PyInstaller,
  smoke test, zip, SHA-256) producing `dist/IconReplacer-<version>-win64.zip`.
- Ship LICENSE, `THIRD_PARTY_NOTICES.md` and `README-PORTABLE.txt` inside the zip.
- Add PyInstaller as a dev dependency and a `build` pytest marker.

## Capabilities

### New Capabilities
- `portable-distribution`: layout, contents, build reproducibility and portable-mode
  behavior of the release archive.

### Modified Capabilities

## Impact

- New: `packaging/`, `tools/build_release.py`, `THIRD_PARTY_NOTICES.md`, tests.
- `pyproject.toml`/`uv.lock`: PyInstaller dev dependency, `build` marker.
- No change to runtime application code.
