# Design

## Context

See proposal.md. Wave 1 runs four feature changes in parallel worktrees: `core-folder-icon`, `system-dll-source`, `icon-converter` and `settings-i18n`. They may only meet through `core/`.

## Decisions

- **`core/paths.py`:**
  - `app_dir()` returns the frozen executable's directory when running under PyInstaller, or the repository root in development.
  - `data_root()` applies the override, then portable, then LOCALAPPDATA rule. Writability is probed by creating and deleting a uniquely named temp file inside `app_dir` itself. That is R0, because it stays inside the app directory.
  - `settings_path()`, `cache_dir(name)` and `log_dir()` create directories lazily.
  - The result is memoized per process, and `reset_cache()` is available for tests.
  - In development, the app directory is the repository, so data goes to `<repo>/data`, which is git-ignored.
- **Payload model:** `IconPayload` is a frozen dataclass with these fields:
  - `kind` (`resource` | `ico`);
  - `location: str | None`, an environment-variable path such as `%SystemRoot%\System32\imageres.dll`;
  - `resource_id: int | None`, the positive ID; desktop.ini stores it negated;
  - `ico: bytes | None`.

  The `IconPayload.resource(...)` and `IconPayload.from_ico(...)` constructors validate that exactly one form is set. They reject empty ICO data and data that does not start with the ICO header `00 00 01 00`.
- **`IconMaterializer` Protocol:** `materialize(entry, options) -> IconPayload`. The folder service depends only on this.
- **Alternative considered:** passing a file path for external icons. It was rejected because the folder service must own where the `.ico` is placed (inside the target folder), so it needs bytes.

## Risks / Trade-offs

- [The writability probe can be wrong on folders with odd ACLs] → `ICONREPLACER_HOME` gives an explicit override.
