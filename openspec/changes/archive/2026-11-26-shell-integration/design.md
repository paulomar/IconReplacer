## Context

Portable app, no installer, no admin. Explorer launches static verbs once per selected item in separate processes.

## Decisions

- Registry access goes through a small `RegistryBackend` protocol (`WinregBackend` real, fake in tests). The real backend is hard-locked to the single allowed key path; any other path raises.
- Command line: frozen -> `"<exe>" --folder "%1"`; dev -> `"<.venv>\Scripts\pythonw.exe" -m iconreplacer --folder "%1"` (falls back to `sys.executable`). Status compares the launcher parsed from the stored command to the current launcher (case-insensitive) and checks it exists.
- Explorer on Windows 11 shows static verbs under "Show more options"; we do not use the IExplorerCommand/packaged route.
- Single instance: `QLocalServer`/`QLocalSocket`, name `IconReplacer-<sha1(user SID or username)[:16]>`, user-only socket option. Protocol: 4-byte big-endian length + UTF-8 JSON list of strings, max 64 KB. `connect_or_serve` tries the client path first (short timeouts); on failure it listens (removing a stale server first). `SingleInstance` emits `folders_received(list)`.
- Aggregation: the first instance starts a 400 ms collection timer; folders received during it are merged before the window is created (`collect_startup_folders`), later arrivals are emitted to the window callback.
- CLI flags handled in `__main__` before importing `app`, using only `shell.registration` (stdlib), so no Qt GUI import.

## Risks

- Qt `shell.ipc` imports QtNetwork only when used by the app, not by CLI registration commands.
- A moved app leaves a stale entry until re-registered (surfaced through `status()`).
