## Why

The online and local sections of the icon browser are still mock data. Users need real
icon sources beyond the Windows libraries: public icon sets (Iconify, Phosphor), GitHub icon
repositories, and their own folders of icons.

## What Changes

- Add a hardened, allow-listed HTTPS client with a global "network allowed" switch.
- Add an on-disk cache (hashed file names, 24 h index TTL, stale-while-revalidate) for online sources.
- Add Iconify sources: free search across all collections and the Phosphor collection (regular weight).
- Add GitHub repository sources (defaults `LaviMahal/WindowsIcons`, `sameerasw/folder-icons`).
- Add a local folder source (images and icon libraries) scanned in the background.
- Add a builder that creates the default external sources and helpers to add/remove local folders and parse repository references.
- All sources implement `IconSource`, `DynamicIconSource` and `IconBytesProvider`; Iconify sources also `SearchableIconSource`.

## Capabilities

### New Capabilities
- `external-icon-sources`: network, GitHub and local-folder icon sources with caching, offline behavior and safe handling of remote data.

### Modified Capabilities

None. The core contracts are used unchanged.

## Impact

- New modules under `src/iconreplacer/catalog/` and data under `src/iconreplacer/catalog/external_data/`.
- New tests `tests/test_external_*.py` with trimmed recorded fixtures; a `network` pytest marker (skipped by default).
- The UI wiring is done by a separate change; no UI, settings or service code is touched.
