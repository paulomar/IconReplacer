# Proposal

## Why

The product promise is an Explorer right-click "Replace Icon" entry. Today the app only accepts `--folder` arguments; nothing registers the context-menu verb, and Explorer launches a static verb once per selected folder, so multi-select would open many windows.

## What Changes

- Add a `shell` package that registers/unregisters a per-user static verb on folders (`HKCU\Software\Classes\Directory\shell\IconReplacer`), reports registration status (not registered / registered / stale after the portable app was moved).
- Add single-instance aggregation over a per-user local socket so several launches (multi-select) merge into one window.
- Add CLI flags `--register`, `--unregister`, `--status` that run without opening a window or importing Qt GUI modules.
- Minimal hook in `app.py` to start the single-instance server and append received folders.

## Capabilities

### New Capabilities
- `explorer-integration`: per-user Explorer folder context-menu verb, its status/stale detection, CLI management flags, and single-instance folder aggregation.

### Modified Capabilities

## Impact

- New code in `src/iconreplacer/shell/`, edits in `cli.py`, `__main__.py`, a tiny hook in `app.py`.
- Writes only `HKCU\Software\Classes\Directory\shell\IconReplacer` (risk level R1); no admin, no HKLM, no Explorer restart.
- On Windows 11 the entry appears under "Show more options" (classic menu); the new menu is not hacked.
