# Tasks

## 1. Wiring

- [x] 1.1 Point `extra_sources_factory` at `real_extra_sources` and `local_source_factory` at `LocalFolderSource`, and call `shutdown_all` on quit; verify with tests that the default factory yields iconify, phosphor and both GitHub ids without network calls, that the local factory returns a local source, and that the shutdown hook is connected
- [x] 1.2 Move the app icon drawing into `ui/app_icon.py`, use it for the window icon, and make `packaging/make_app_icon.py` import it; verify with tests that the window icon is not null and that the packaging icon still builds all sizes

## 2. Release

- [x] 2.1 Run ruff and the full pytest suite, regenerate translations, and check the screenshots; verify that all are clean
- [x] 2.2 Bump to 1.0.0.13, archive, merge and tag, then build the release zip with `tools/build_release.py`; verify the smoke-test output and the checksum file
