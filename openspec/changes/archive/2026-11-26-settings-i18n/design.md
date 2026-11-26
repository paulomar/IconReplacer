## Context

`SettingsStore` (get/set protocol) exists with an in-memory implementation. The data root and `settings_path()` are provided by `core.paths`.

## Goals / Non-Goals

**Goals:** durable, safe settings; restore UI state; language selection with restart.
**Non-Goals:** live language switching; debounced saving; settings migration (schema version 1 only).

## Decisions

- `JsonSettingsStore` in `iconreplacer.settings` implements the existing protocol, so `MainWindow` keeps accepting any store. A registry maps each known key to a default and a coercer that raises on invalid input; invalid values log a warning and fall back to the default.
- Saves happen synchronously on every `set` (settings are tiny and changes are rare) and on close; writes go to a temp file in the same directory and `os.replace`. A save failure is logged, never raised.
- Corrupt files are renamed to `settings.json.corrupt-<timestamp>` and defaults are used.
- Geometry is stored as base64 `saveGeometry()` and restored only if the resulting window frame intersects an available screen geometry enough to be reachable; otherwise the default size is kept.
- Language: `ui.language` empty resolves to the system locale if a `.qm` exists, else English. A restart note label in Settings is shown when the combo changes.
- `tools/update_translations.py --release` runs `pyside6-lrelease` for every `.ts` into the i18n directory; `.qm` stays git-ignored.
- Disabled sources are persisted by id; local folders are persisted and re-registered at startup as the prototype mock local sources.

## Risks / Trade-offs

- Synchronous save on every set could be slow for frequent changes such as the size slider; the slider persists on release/close only is not needed given tiny file size, but it is saved on value change. Acceptable.
