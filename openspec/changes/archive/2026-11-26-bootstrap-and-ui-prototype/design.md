# Design

## Context

The repository is greenfield. It holds one commit, an initialized OpenSpec, and a default branch named `master`. The machine runs Windows 11 with Python 3.14 and `uv`. See proposal.md for the motivation. This change sets up the foundation that every later feature change plugs into. The aim is to let later changes run in parallel worktrees. To make that possible, this change also defines the **internal contracts** (data model and service interfaces) that those changes implement, so they do not collide on shared files.

## Goals / Non-Goals

**Goals:**
- A runnable PySide6 app (`python -m iconreplacer`), with tests that run headless (`QT_QPA_PLATFORM=offscreen`).
- Stable internal contracts: `IconEntry`, `IconSource`, `FolderIconService` and `SettingsStore`. Later changes provide real implementations and do not reshape the UI.
- A UI that is convincing enough to validate the layout, density and theme.

**Non-Goals:**
- Real icon extraction, conversion, network access, desktop.ini writes, registry writes or packaging. Each of these is a later change.
- Persisting settings. The prototype keeps settings in memory.
- Shipping any Microsoft icon artwork. The mock icons are drawn procedurally.

## Decisions

### D1. Package layout and contracts
```
src/iconreplacer/
  __init__.py
  __main__.py          # python -m iconreplacer
  version.py           # single source: VERSION = (0, 1, 0, 1)
  cli.py               # argparse: --folder (repeatable), --version
  app.py               # QApplication bootstrap, theme, translator
  core/
    models.py          # IconEntry, IconRef, Category (frozen dataclasses)
    contracts.py       # IconSource, FolderIconService, SettingsStore (Protocols)
  catalog/
    mock_source.py     # procedural mock IconSource (10k capable)
    registry.py        # SourceRegistry: aggregates IconSources
  services/
    mock_folder_service.py  # simulated apply/undo/restore (no I/O)
  ui/
    main_window.py  sidebar.py  icon_grid.py (model+proxy+delegate)
    preview_panel.py  target_header.py  settings_view.py
    about_dialog.py  theme.py  folder_base.py (QPainterPath folder shape)
  i18n/                # .ts sources; .qm compiled later
tests/
tools/bump_version.py  # BUILD/MINOR/PATCH bump, rewrites version.py
```
**Why:** every later change owns a separate area:
- `catalog/<source>.py` for `system-dll-source` and `external-sources`;
- `services/` for `core-folder-icon`;
- `converter/` for `icon-converter`;
- `shell/` for `shell-integration`;
- `settings/` for `settings-i18n`.

They meet only through `core/contracts.py`. That keeps parallel worktrees almost free of conflicts.

**Alternative considered:** a flat module set. It was rejected because parallel changes would all edit the same files.

### D2. `IconEntry` model
A frozen dataclass with these fields: `id`, `name`, `source_id`, `ref`, `categories: frozenset[str]`, `tags: frozenset[str]`, `license`, `kind` (`"glyph"` | `"full"`). `ref` is an `IconRef(kind, location, resource_id)`.

The `kind` field lets the preview decide whether a folder base makes sense by default. `IconSource.render(entry, size) -> QImage` is the only way to get pixels, which lets sources render lazily.

### D3. Virtualized grid
The grid uses `QListView` in `IconMode` with `setUniformItemSizes(True)`. Data comes from a `QAbstractListModel` behind a `QSortFilterProxyModel`, which applies the source, category and search filters. A custom `QStyledItemDelegate` paints each item, and an LRU pixmap cache is keyed by `(id, size)`.

**Why:** only visible items get painted, so 10k+ items stay responsive. This approach is Qt-native and needs no extra dependency.

**Alternative considered:** a `QGraphicsView` or QML grid. QML would be smoother, but it is a second technology, packaging gets heavier, and widgets are easier to test with pytest-qt.

### D4. Theme
The app uses the Fusion style with two `QPalette` definitions plus a small QSS file. The initial scheme comes from `QStyleHints.colorScheme()`, and the app listens to `colorSchemeChanged` to follow the system. A user override replaces the palette at runtime.

The look is technical and dense: a monospace font for IDs and paths, an accent color, 4 px radii and visible metadata.

**Alternative considered:** PyQt-Fluent-Widgets. Its GPL edition conflicts with the MIT license.

### D5. Folder-base composition
`ui/folder_base.py` draws an original Win11-*style* folder from a `QPainterPath` (a back flap, a front panel and a tint gradient). The glyph is scaled to about 55% and centered on the front panel. The same function becomes the core of `icon-converter` later, so it is written as a pure function that returns a `QImage`, with no widget code.

### D6. i18n
All strings go through `self.tr()` or `QCoreApplication.translate()`. The source strings are English. `pyside6-lupdate` produces `i18n/iconreplacer_en.ts`. The language list in Settings is built by scanning the available `.qm` files, plus English as the built-in language.

### D7. Versioning
`version.py` holds `VERSION = (MAJOR, MINOR, PATCH, BUILD)` and the derived strings. `pyproject.toml` takes its version dynamically from this file through hatchling, and PEP 440 accepts `0.1.0.1`.

`tools/bump_version.py {build|patch|minor|major}` always increments BUILD and optionally also increments the named part. It runs on the feature branch just before the merge into `main`, and the merge is then tagged `v<version>`.

### D8. Simulated actions
`MockFolderIconService` implements the `FolderIconService` contract. It records the calls in memory and returns a result that describes what would happen. It performs no file or registry I/O. A test asserts that no file is touched.

### D9. Git
1. `git branch -m master main`. This is R0, local only, with no remote.
2. Create `feat/bootstrap-and-ui-prototype` from `main`.
3. Commit the OpenSpec artifacts and the scaffold on that branch.
4. After validation, merge into `main` and tag `v0.1.0.1`.

## Risks / Trade-offs

- [Procedural mock icons look less real than system icons] → Use clear glyph shapes, colors and a folder base. Real icons arrive in `system-dll-source`, and the layout is what is being validated now.
- [PySide6 wheel availability for Python 3.14] → If `uv add pyside6` fails on 3.14, pin the project to Python 3.13 via `uv python install 3.13`. That is R0, because it goes into the uv-managed directory and not a global install. Record the fallback in the README.
- [Headless rendering differs from on-screen rendering] → Take the validation screenshots with `QWidget.grab()` on a real display session, with no offscreen platform, and save them under `docs/screenshots/`.
- [The contracts may need to change once the real sources land] → Keep the contracts minimal. Later changes can extend them through ADDED fields that have defaults.

## Migration Plan

Not applicable (greenfield). Rollback means resetting `main` to the previous tag. Every step is R0.
