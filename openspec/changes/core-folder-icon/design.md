# Design

## Context

`core/contracts.py` defines `FolderIconService` (`apply` / `undo` / `restore_default` returning `ActionResult`) and `IconMaterializer` (entry + options -> `IconPayload`). `IconPayload` is either a RESOURCE (location + positive resource id) or ICO bytes. Only a mock implementation exists so far. The contracts stay unchanged; see proposal.md for the motivation.

## Goals / Non-Goals

**Goals:**
- A ctypes-only Windows implementation with explicit `argtypes`/`restype` and HRESULT/BOOL checks.
- Undo that restores files and attributes byte for byte.
- Safety checks that live in their own pure module so they are easy to test.

**Non-Goals:**
- Wiring the service into the UI or Explorer context menu.
- Rendering or composing icons (that is the materializer's job).
- Elevated operations, the registry, the icon cache and restarting Explorer.

## Decisions

### Modules
- `services/win32_shell.py`: thin ctypes bindings (`get_attributes`, `set_attributes`, `set_folder_icon` (SHGetSetFolderCustomSettings), `notify_updated` (SHChangeNotify)), wrapped in a `Win32Shell` class. The service takes the shell object as a constructor argument, so tests can inject a shell whose API call fails and exercise the fallback writer.
- `services/folder_safety.py`: `check_folder(path) -> Path` raises `UnsafeFolderError(reason)`; it reads environment variables at call time so tests can monkeypatch them.
- `services/folder_icon_service.py`: `WindowsFolderIconService(materializer, shell=None)`, the desktop.ini editor (`IniDocument`) and the history store.

### Write mechanism: SHGetSetFolderCustomSettings first, own writer as fallback
A spike (repeated in `test_folder_icon_spike.py`) showed that `SHGetSetFolderCustomSettings(FCSM_ICONFILE, FCS_FORCEWRITE)` accepts both the relative `.iconreplacer\icon.ico` path and `%SystemRoot%` paths and writes them verbatim. The call also sets the folder ReadOnly and desktop.ini Hidden|System. It goes through the profile API, which preserves other sections and a UTF-16 file. We use the API when the icon string is ASCII. Otherwise, or when the API fails, we use our own writer. The profile API would degrade non-ASCII text to `?` in an ANSI file. Before calling the API, legacy `IconFile`/`IconIndex` keys are removed with our editor, so `IconResource` is the only icon key.
*Alternative:* always use our own writer. That is deterministic, but it gives up the documented shell behaviour, so we keep it as the fallback only.

### desktop.ini editor
The editor works line by line and keeps every untouched line, the newline style and the encoding (detected from the BOM: UTF-16 LE, UTF-8 with BOM, otherwise ANSI through `mbcs`). If the new text cannot be encoded in ANSI, or is non-ASCII, the file becomes UTF-16 LE with a BOM, which is what Explorer reads for Unicode. Section and key matching ignores case.

### History record
`.iconreplacer\history.json` = `{"version": 1, "owned_attributes": int, "entries": [...]}` (newest last, at most 10). Each entry contains `desktop_ini` (base64 or null), `desktop_ini_attributes`, `folder_attributes`, `icon` (base64 or null) and `store_existed`. `owned_attributes` collects the folder ReadOnly/System bits that IconReplacer turned on. It lives at the top level so that trimming old entries never loses it. Both history.json and icon.ico are written to a temporary file and then moved with `os.replace`.
Undo pops the newest entry and restores it. If `store_existed` is false, `.iconreplacer` is deleted entirely; otherwise the icon is restored (or removed) and the history is rewritten. Attribute restore only touches the settable bits (ReadOnly, Hidden, System, Archive, NotContentIndexed).

### Safety resolution
`os.path.abspath` first removes `..` segments without following links. Each component from the target up to the anchor is then checked with `os.lstat` for a *name-surrogate* reparse tag (symlink, junction or mount point). Cloud placeholders such as OneDrive folders, which use non-surrogate tags, stay allowed. After that, `Path.resolve(strict=True)` expands short names. Comparison uses `os.path.normcase` on resolved paths. Write permission is checked by creating and deleting a uniquely named probe file in the folder.

### Batch result
The materializer is called once per apply. Each folder is processed in a `try` block that catches `UnsafeFolderError` and `OSError`. On success the result message is "Applied to N folder(s)."; on failure it is "Done on X of N folders. Failed: <name>: <reason>; ...". `affected` lists the successful folders.

## Risks / Trade-offs

- [Explorer may keep a cached icon when only the content of `icon.ico` changes] -> We send `SHCNE_UPDATEITEM` and `SHCNE_UPDATEDIR` for the folder. A per-apply unique file name is a possible follow-up if testing shows stale icons.
- [The write-probe touches the folder's modification time] -> We are about to write there anyway, and the probe file is deleted right away.
- [desktop.ini edited by another tool between apply and undo] -> Undo restores our snapshot, which overwrites that edit. This is the documented behaviour.
- [Network shares without attribute support] -> Errors are reported per folder and never abort the batch.
