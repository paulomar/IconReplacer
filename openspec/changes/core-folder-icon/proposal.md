# Proposal

## Why

The UI only talks to `MockFolderIconService`, which only simulates changes. IconReplacer needs a real Windows folder icon writer before the Explorer integration can do anything useful. That writer has to be safe: it must back up the previous state, allow undo, and refuse system folders, as `openspec/config.yaml` requires.

## What Changes

- Add a real `FolderIconService` implementation for Windows. It applies an icon to one or more folders, undoes the last change, and restores the default icon.
- Write resource icons as `IconResource=<location>,-<id>` and keep environment-variable forms such as `%SystemRoot%` unexpanded.
- Store generated ICO icons inside the target folder (`.iconreplacer\icon.ico`) and reference them with a relative path, so the icon still works after the folder is moved or copied to another PC.
- Keep a bounded per-folder history in `.iconreplacer\history.json`. Each entry holds the exact previous desktop.ini bytes, the attributes and the previous icon file, so undo restores the folder byte for byte.
- Add safety checks that refuse drive roots, system and program folders, the user profile root, symlinks and junctions, missing paths and folders that cannot be written. Each refusal comes with a clear reason.
- Notify Explorer after every change. The service never asks for elevation and never touches the registry, the icon cache or explorer.exe.

## Capabilities

### New Capabilities
- `folder-icon-apply`: applying, undoing and resetting custom folder icons on Windows, including the safety rules, the history and the format written to desktop.ini.

### Modified Capabilities
_None._

## Impact

- New modules: `src/iconreplacer/services/folder_icon_service.py`, `win32_shell.py` (ctypes bindings to shell32/kernel32) and `folder_safety.py`.
- New tests: `tests/test_folder_icon_*.py`. They only touch folders that the tests create under pytest `tmp_path`.
- No changes to the contracts in `core/`, to the UI or to dependencies. Wiring the service into the app is left to a later change.
