# Tasks

## 1. Win32 bindings

- [x] 1.1 Implement `services/win32_shell.py` (attributes, SHGetSetFolderCustomSettings, SHChangeNotify, explicit argtypes/restype, OSError on failure) and verify `tests/test_folder_icon_spike.py` passes: a relative and a `%SystemRoot%` IconResource are written verbatim and the Hidden|System/ReadOnly attributes are set on tmp_path folders

## 2. Safety checks

- [x] 2.1 Implement `services/folder_safety.py` and verify `tests/test_folder_icon_safety.py` passes for every refusal rule (missing, file, drive root, Windows/Program Files/ProgramData via monkeypatched env vars and `..` paths, profile root vs subfolder, junction, unwritable) and for an allowed folder

## 3. desktop.ini editor and history

- [x] 3.1 Implement the line-preserving `IniDocument` (encoding detection, set/remove keys, UTF-16 upgrade for non-ASCII) and verify `tests/test_folder_icon_ini.py` round-trips ANSI, UTF-8-BOM and UTF-16 files and keeps unrelated sections
- [x] 3.2 Implement the bounded history store (snapshot, push, pop, owned attributes, atomic writes) and verify the history-limit test in `tests/test_folder_icon_service.py` passes

## 4. Folder icon service

- [x] 4.1 Implement `WindowsFolderIconService.apply` (resource and ICO payloads, API with fallback writer, Explorer notification, batch aggregation) and verify the apply, preservation, unicode, idempotence, fallback-writer and batch tests in `tests/test_folder_icon_service.py` pass
- [x] 4.2 Implement `undo` and verify the byte-identical undo tests (first apply, second apply, nothing to undo) pass
- [x] 4.3 Implement `restore_default` and verify the cleanup and keep-other-keys tests pass
- [x] 4.4 Store ICO payloads as content-addressed `icon-<sha256[:12]>.ico`, delete unreferenced `icon-*.ico` on apply and snapshot every icon file name and its bytes; verify these tests pass: `test_reapplying_different_ico_changes_file_name`, `test_undo_second_apply_restores_first` (old name and file back) and `test_repeated_apply_is_idempotent` (same name)

## 5. Integration checks

- [x] 5.1 Run `uv run pytest -q`, `uv run ruff check` and `uv run ruff format --check` and verify they all pass; run `openspec validate core-folder-icon --strict` and verify it is valid
