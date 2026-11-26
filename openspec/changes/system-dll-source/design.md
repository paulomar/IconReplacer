# Design

## Context

`catalog/mock_source.py` provides procedural sources and owns the `SYSTEM_LIBRARIES` metadata. `core/contracts.IconSource` is the only interface the UI uses. Folder icons are stored in `desktop.ini` as `IconResource=<path>,-<id>`. That syntax requires an integer resource ID, which is why entries carry `IconRef(RESOURCE, "%SystemRoot%\System32\<file>", id)`.

**Spike (Windows 11 build 26300).** Since Windows 10 1903, the System32 copies of several libraries are tiny stubs. For example, `imageres.dll`, `wmploc.dll`, `mmres.dll`, `dmdskres.dll` and `moricons.dll` are each 12 KB, and their resources live in `%SystemRoot%\SystemResources\<file>.mun`. Loading the System32 stub with `LoadLibraryExW(LOAD_LIBRARY_AS_DATAFILE | LOAD_LIBRARY_AS_IMAGE_RESOURCE)` exposes the `.mun` resources transparently: the loader redirects resource lookups. As a result, `EnumResourceNamesW` returns the same groups for the stub and for the `.mun` file. For example, it returns 367 groups for imageres, 2 of them string-named. Enumeration takes about 1 to 5 ms per library. `pnidui.dll` is not present on this build.

## Goals / Non-Goals

**Goals**
- Real `IconSource` implementations.
- Correct rendering at any size.
- `.ico` export.
- Fast lazy loading.
- Curated classification.

**Non-Goals**
- Wiring the sources into the UI or the registry.
- Writing `desktop.ini`.
- Thumbnail caching on disk.
- Icon similarity search.

## Decisions

1. **Load the System32 path first, and fall back to the `.mun` file.** The spike shows that the loader redirect works. Loading `System32\<file>` keeps the code honest: it uses exactly what Explorer resolves. When that load fails, or the stub exposes no groups, the source loads `SystemResources\<file>.mun` directly instead. This covers older builds and odd redirect behaviour. Alternative considered: always parse `.mun` files directly. That path is not what Explorer resolves, and some libraries have no `.mun` file at all (setupapi, pifmgr, powrprof, shdocvw).
2. **ctypes, not pywin32 or a pure-Python PE parser.** It adds no dependency (MIT-friendly), and the OS loader already handles the MUI redirect. `kernel32` calls are typed explicitly to stay 64-bit safe. Callbacks are kept alive while the enumeration runs.
3. **Integer IDs only.** `,-<id>` cannot address string-named groups, so those groups are counted and skipped.
4. **Companions are separate sources.** `powrprof.dll`, `mstsc.exe` and `shdocvw.dll` are distinct files. Explorer needs the exact file in the reference, so each one becomes its own source with `companion_of` metadata, for example `powrprof.dll` is a companion of `powercpl.dll`. The UI can group them later. Source IDs are the lower-cased file name, the same as the mock IDs, so that swapping the mock for the real source is transparent.
5. **ICO assembly.** For each group, `GRPICONDIR` is converted into `ICONDIR`/`ICONDIRENTRY`. The 2-byte resource ID of each `RT_ICON` is replaced with a 4-byte offset, and the payloads are appended as-is. PNG payloads report their real size from the IHDR chunk.
6. **Rendering.** The source picks the best image from the group directory:
   - an exact width, preferring the highest bit depth;
   - otherwise the smallest larger image;
   - otherwise the largest image.

   That single image is then decoded. A PNG payload is decoded directly, and a BMP payload is wrapped in a one-entry ICO decoded by Qt's ICO plugin. The result is scaled with `SmoothTransformation` and centred on a transparent `size x size` canvas in `ARGB32_Premultiplied`. Decoding only the chosen image avoids depending on Qt's choice among multiple ICO frames. A small LRU cache (256 items) keeps assembled ICO bytes for each source.
7. **Index cache.** Each library gets its own JSON file in `paths.cache_dir("system")`. The cache key contains:
   - the format version;
   - the resolved path, size and mtime (in ns) of the System32 file;
   - the same values for the `.mun` file when one exists, because Windows updates can change the `.mun` file without touching the stub.

   The file stores each group's ID, its sizes and a short blake2b hash of the group content (directory plus payloads), plus the number of skipped string-named groups. A missing, corrupt or stale file is rebuilt silently. Writes are atomic: the file is written to a temporary file, then `os.replace` puts it in place. Write errors are ignored, since the cache is only an optimisation.
8. **Classification.**
   - `system_libraries.json` holds `categories` for each library. This is what the library contains, used in the sidebar description. It also holds `default_categories`, which are applied to uncurated entries.
   - `system_icon_tags.json` maps `library -> id -> {name, categories, tags}` for well-known imageres and shell32 IDs. These were curated by visually inspecting the icons rendered to the ignored `data/` scratch directory.
   - Curated categories replace the defaults. Every entry's tags include the library name, the ID and the lower-cased categories.
   - No image heuristic is used. Curation plus library defaults was judged precise enough, and a colour or shape heuristic would mislabel too often.
9. **Lifecycle and threading.** A `PeModule` holds the HMODULE and an `RLock`. The source opens it lazily on the first `entries()` or `render()` call. A warm cache start does not load the module until the first render. `close()` frees the module and is idempotent; a later render reopens it. `build_system_sources()` returns only the sources whose files exist.

## Risks / Trade-offs

- [The MUI redirect behaviour changes in a future build] → The source falls back to loading the `.mun` file directly. Tests assert that imageres exposes more than 300 groups.
- [Resource IDs differ between Windows builds] → The curated mapping is advisory. Entries are always enumerated from the live file, and curated IDs that are missing are ignored.
- [The Qt ICO plugin is missing from a frozen build] → BMP payloads would fail to decode. The packaging change must include `imageformats/qico.dll`. If decoding fails, `render` returns a transparent image of the requested size instead of raising.
- [Many open modules] → Each mapped image uses address space but very little memory. `close()` is available, and modules open only on demand.

## Migration Plan

This change is additive. The UI keeps the mock sources until a follow-up change registers `build_system_sources()`. To roll back, remove the new modules.
