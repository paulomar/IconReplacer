## Why

User preferences (theme, thumbnail size, sources panel, window geometry, enabled sources, network switch, language) are lost on every start because settings live only in memory. Users also cannot actually change the language. This change persists settings and makes the language selectable.

## What Changes

- Add a JSON settings store persisted at the settings path of the data root, with typed defaults, validation, unknown-key preservation, atomic writes and corrupt-file recovery.
- Restore theme, sources-panel visibility, window geometry (only when it fits a current screen), thumbnail size, disabled sources and the network switch at startup, and persist them on change and on exit.
- Persist the language choice; it takes effect on the next start, and Settings shows a restart note when it changes. An empty language follows the system locale when a translation exists, else English.
- Add a tool to compile `.ts` translations into `.qm` files (build output, git-ignored).

## Capabilities

### New Capabilities
- `app-settings`: persistence, validation and recovery of user settings, and restoring them in the UI.

### Modified Capabilities
- `icon-browser-ui`: translatable UI requirement now covers language selection, persistence and the restart note.

## Impact

- New package `src/iconreplacer/settings/`; changes in `app.py`, `ui/main_window.py` (restore/save only), `ui/settings_view.py`, `tools/`, i18n template and tests.
