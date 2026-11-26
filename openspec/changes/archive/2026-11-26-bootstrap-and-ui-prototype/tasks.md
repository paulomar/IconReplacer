# Tasks

## 1. Repository and project setup

- [x] 1.1 Rename branch `master` to `main` and create `feat/bootstrap-and-ui-prototype`; verify with `git branch --show-current`
- [x] 1.2 Add the `context` block of durable project constraints to `openspec/config.yaml`; verify that `openspec context --json` still resolves the root
- [x] 1.3 Create `pyproject.toml` with hatchling, a dynamic version from `src/iconreplacer/version.py`, the MIT `LICENSE`, a Python `.gitignore` and a README skeleton; verify that `uv sync` succeeds
- [x] 1.4 Add the dependencies: `pyside6` as runtime, and `pytest`, `pytest-qt`, `ruff` as dev, all in the project `.venv`. If 3.14 has no wheels, fall back to 3.13 as in design.md. Verify that `uv run python -c "import PySide6"` succeeds

## 2. Versioning and CLI

- [x] 2.1 Implement `version.py` (`VERSION = (0, 1, 0, 1)` plus the derived strings) and `tools/bump_version.py`; verify with tests that the format regex holds, that BUILD always increments and that BUILD does not reset on a minor bump
- [x] 2.2 Implement `cli.py` with a repeatable `--folder` and `--version`; verify with tests that `--version` prints `IconReplacer 0.1.0.1` and exits 0 without creating a window

## 3. Core contracts and mock data

- [x] 3.1 Implement `core/models.py` and `core/contracts.py` (`IconEntry`, `IconRef`, `IconSource`, `FolderIconService`, `SettingsStore`); verify with unit tests for immutability and equality
- [x] 3.2 Implement `catalog/mock_source.py` and `catalog/registry.py`, covering the 22 system libraries from the spec, the online and local mock sources, procedural glyphs and categories, and a 10k mode; verify with tests for per-source counts and category tags
- [x] 3.3 Implement `services/mock_folder_service.py`; verify with a test that apply, undo and restore return descriptive results and that no file in a temporary directory changes

## 4. UI prototype

- [x] 4.1 Implement `ui/theme.py` (Fusion palettes, QSS, following the system, runtime override) and `ui/folder_base.py` (a pure `QImage` composition); verify with tests that the theme switch changes the palette and that the composition returns the requested size
- [x] 4.2 Implement `ui/icon_grid.py` (model, filter proxy, delegate and pixmap cache) and the size slider; verify with pytest-qt that combined source, category and search filtering works, that the empty state appears, and that 10k items filter in under 300 ms
- [x] 4.3 Implement `ui/sidebar.py` (System libraries / Online sources / Local folders / All, with counts) wired to the grid; verify with a test that selecting imageres.dll shows a count equal to the grid row count
- [x] 4.4 Implement `ui/preview_panel.py` (sizes 16 to 256, metadata, compose toggle, tint picker); verify with a test that all seven sizes are rendered and that the toggle changes the image
- [x] 4.5 Implement `ui/target_header.py` and the mocked Apply/Undo/Restore actions; verify with tests for "3 folders" in batch mode and for "No target folder" with Apply disabled
- [x] 4.6 Implement `ui/settings_view.py` (sources, network switch, language list from the available translations, theme selector) and `ui/about_dialog.py`; verify with tests that turning the network off greys out the online sources and that About shows the version text and the PySide6 notice
- [x] 4.7 Implement `ui/main_window.py` and `app.py` (resizable, minimum size of at most 800x560, reflow); verify with a test for the minimum size and that columns increase when the window gets wider
- [x] 4.8 Run `pyside6-lupdate` to produce `src/iconreplacer/i18n/iconreplacer_en.ts`; verify that the template contains the strings from the main window, Settings and About

## 5. Validation and release

- [x] 5.1 Run `uv run ruff check` and `uv run pytest`; verify that both are clean
- [x] 5.2 Capture screenshots (main window in light and dark, preview with composition, batch header, Settings, About) to `docs/screenshots/` and update the README; verify that the files exist
- [x] 5.3 Commit on the feature branch, merge into `main`, tag `v0.1.0.1`, delete the feature branch, then PAUSE for user visual validation
