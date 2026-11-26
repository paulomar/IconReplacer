# Proposal

## Why

Every building block now exists: real system icon sources, the converter, the real
`WindowsFolderIconService`, settings and the Explorer verb registration. The window still runs
on mock sources and a simulated service, so the product cannot do its one job. This change
turns the validated prototype into the real application.

## What Changes

- New `CompositeMaterializer` that turns a chosen icon into an `IconPayload` by asking the
  entry's own source: resource icons are referenced in place (or composed from the source's
  pixels), other icons come from sources that provide raw bytes and go through the converter.
- `app.py` builds the real catalog (system libraries plus an injectable
  `extra_sources_factory(settings)` hook, empty by default) and the real
  `WindowsFolderIconService`. Mock sources and the simulated service are only used when
  `ICONREPLACER_DEMO=1` (tests and screenshots).
- Local folder sources are created through an injectable `local_source_factory(path)`; without
  one the "Add local folder…" control is hidden.
- Generic support for `DynamicIconSource` (subscription, network switch, refresh, sidebar state
  badges) and `SearchableIconSource` (debounced remote search on the selected source), without
  importing any concrete online source module.
- **BREAKING** (prototype behaviour): Apply, Undo and Restore default really modify the target
  folders. They run in a worker thread with a busy indicator, ask for confirmation for batches,
  report a success count and show a per-folder failure details dialog.
- "Choose folders…" in the target header so the app is usable without `--folder`.
- Settings gain an "Explorer integration" group (status, Register / Re-register / Unregister);
  a stale registration shows a non-blocking "Fix Explorer integration" banner at startup.
- About lists the converter and system-data notices and the third-party icon source license
  caveat.
- Screenshots use the real system icons with demo targets and the simulated service; README no
  longer says "prototype" and documents the Explorer menu registration.

## Capabilities

### New Capabilities

### Modified Capabilities
- `icon-browser-ui`: real folder actions (replacing the simulated requirement), choosing target
  folders, real catalog by default, dynamic source status, remote search, conditional local
  folder control in Settings.
- `folder-icon-apply`: the chosen icon is resolved into a payload through its own source.
- `explorer-integration`: registration management and stale-registration banner in the UI.
- `app-versioning`: About lists converter, system-data and third-party source license notices.

## Impact

- New: `src/iconreplacer/services/materializer.py`, `src/iconreplacer/services/apply_worker.py`,
  `src/iconreplacer/ui/result_dialog.py`.
- Changed: `app.py`, `ui/main_window.py`, `ui/target_header.py`, `ui/settings_view.py`,
  `ui/sidebar.py`, `ui/icon_grid.py`, `ui/about_dialog.py`, `ui/strings.py`, i18n template,
  `tools/screenshots.py`, README, UI tests.
- Side effects: the application now writes `desktop.ini` / `.iconreplacer` in folders the user
  picked, and writes the per-user Explorer verb key only when the user asks. Tests keep R0/R1:
  real folder changes only under `tmp_path`, registry through a fake backend.
- No new dependencies; no contract changes in `core/`.
