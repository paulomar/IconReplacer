# Proposal

## Why

The next wave builds four features in parallel: folder icon apply, system DLL source, icon converter and settings. Two things are missing for that to work without conflicts:
- They need to agree on where the portable app stores its data and cache.
- They need a common way to describe "the icon that will be written to a folder".

Defining both up front keeps each feature in its own files.

## What Changes

- A storage-location policy:
  - When the app directory is writable, data and cache live next to the app, which is portable mode.
  - Otherwise they fall back to `%LOCALAPPDATA%\IconReplacer`.
  - The `ICONREPLACER_HOME` environment variable overrides both. Tests and power users can use it.
- New internal contracts:
  - `IconPayload`: either a system resource reference (`location` + resource id) or ready-to-write `.ico` bytes.
  - `IconMaterializer`: turns an `IconEntry` plus `ApplyOptions` into an `IconPayload`.
- `.worktrees/` is git-ignored so that parallel feature worktrees can live inside the repository.
- Version 0.1.2.3.

## Capabilities

### New Capabilities
- `app-storage-locations`: where IconReplacer keeps its settings, caches and logs, and how portable mode is decided.

### Modified Capabilities
<!-- none -->

## Impact

- New `src/iconreplacer/core/paths.py`, plus additions to `core/models.py` and `core/contracts.py`, with tests.
- No UI change.
