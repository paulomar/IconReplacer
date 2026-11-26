# Tasks

## 1. PE resource access

- [ ] 1.1 Implement `catalog/pe_icons.py`: `PeModule` (LoadLibraryExW as datafile, EnumResourceNamesW integer ids, FindResource/LoadResource, FreeLibrary on close), `parse_group`, `build_ico`; verify with `tests/test_system_pe.py` (imageres/shell32 enumerate, ICO header, parse back with Qt, closed module raises, non-Windows skip)

## 2. Library metadata and curation

- [ ] 2.1 Add `catalog/data/system_libraries.json` with the 22 libraries plus companions powrprof.dll, mstsc.exe, shdocvw.dll (description, categories, default_categories, companion_of); verify schema test in `tests/test_system_data.py` (all categories canonical, 22 required files present)
- [ ] 2.2 Curate `catalog/data/system_icon_tags.json` (>= 150 imageres/shell32 ids with name, categories, tags) by rendering contact sheets into ignored `data/`; verify schema test (ids positive ints, categories canonical, names non-empty, count >= 150)

## 3. System icon source

- [ ] 3.1 Implement `SystemIconSource` (lazy entries, System32 then `.mun` fallback, classification, license, refs) and `build_system_sources()`; verify `tests/test_system_source.py` (ref format, unique positive ids, categories subset of CATEGORIES, curated names applied, missing library -> 0 entries, factory skips missing)
- [ ] 3.2 Implement `render(entry, size)` and `extract_ico_bytes(entry)` with best-image selection and smooth scaling; verify tests render 16/24/32/48/64/100/256 non-null exact size and exported ICO decodes
- [ ] 3.3 Implement the JSON index cache in `cache_dir("system")` keyed by path+size+mtime (+ .mun stat); verify tests: warm entries equal cold, warm < 100 ms, cold imageres < 1.5 s, stale key rebuilds, corrupt file tolerated

## 4. Integration checks

- [ ] 4.1 Run `uv run pytest -q`, `uv run ruff check`, `uv run ruff format --check` and `openspec validate system-dll-source --strict`; all pass
