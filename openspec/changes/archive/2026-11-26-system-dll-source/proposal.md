# Proposal

## Why

The System libraries section of the icon browser still shows procedural mock glyphs. Users need to browse the icons that Windows already ships in its system libraries, classified by type, and pick one for a folder. The icon must be referenced in place by its resource ID, so that no Microsoft artwork is copied or redistributed.

## What Changes

- A real icon source for each Windows icon library: the 22 libraries from the product research, plus the companion files `powrprof.dll`, `mstsc.exe` and `shdocvw.dll`.
  - Each source reads the library's `RT_GROUP_ICON` resources read-only.
  - It exposes every icon group with an integer ID as an entry. The entry references `%SystemRoot%\System32\<file>` with a positive resource ID.
- Rendering of any system icon at any requested pixel size. The best image in the group is chosen and scaled smoothly when needed.
- Export of a system icon as standalone `.ico` bytes.
- A per-library index cache in the application cache directory, so later startups skip re-enumeration.
- Classification of every icon into the canonical categories:
  - library-level default categories;
  - a curated mapping of well-known `imageres.dll` and `shell32.dll` IDs to names, categories and tags.
- Libraries missing from the running Windows build are skipped without errors.
- Library metadata (descriptions, categories) moves to a data file owned by the system source. The mock source is left untouched.

## Capabilities

### New Capabilities
- `system-icon-library`: discovering, classifying, rendering and exporting the icons stored in Windows system libraries. Icons are referenced in place by resource ID.

### Modified Capabilities
<!-- none: wiring the real source into the UI is a separate change -->

## Impact

- New `src/iconreplacer/catalog/pe_icons.py`, which provides read-only ctypes access to PE resources.
- New `src/iconreplacer/catalog/system_source.py`, which provides `SystemIconSource` and `build_system_sources()`.
- New data files `src/iconreplacer/catalog/system_data/system_libraries.json` and `system_icon_tags.json`.
- New tests `tests/test_system_*.py`. These tests read system DLLs read-only (R0) and use a temporary `ICONREPLACER_HOME`.
- No change to `core/*`, the UI or the version. No new dependencies.
