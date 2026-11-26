## 1. Tooling

- [x] 1.1 Add PyInstaller dev dependency and `build` pytest marker
- [x] 1.2 `packaging/make_version_info.py` (VERSIONINFO from version.py)
- [x] 1.3 `packaging/make_app_icon.py` (QPainter icon, multi-size ICO)
- [x] 1.4 Entry points and `packaging/iconreplacer.spec` (onedir, GUI + CLI companion, generic data, Qt trimming)

## 2. Release pipeline

- [x] 2.1 `tools/build_release.py` (clean, translations, icon, version, PyInstaller, smoke, zip, SHA-256)
- [x] 2.2 `THIRD_PARTY_NOTICES.md`, `README-PORTABLE.txt` template, README "Build a release"

## 3. Tests and verification

- [x] 3.1 Fast unit tests (version info, data collection, icon, zip layout, frozen launcher)
- [x] 3.2 Slow `build` marker end-to-end test
- [x] 3.3 Run the full build once; verify `--version`, `--status`, portable data root
