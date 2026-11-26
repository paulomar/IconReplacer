# Tasks

## 1. Network and cache foundation

- [ ] 1.1 Add `catalog/net.py` (HTTPS-only, host allow-list, redirect validation, timeouts, size limits, typed errors, network-allowed flag); verify with `tests/test_external_net.py` using a fake transport (scheme, host, redirect, size, offline, no transport call)
- [ ] 1.2 Add `catalog/online_cache.py` (hashed names, atomic writes, TTL, stale detection); verify with `tests/test_external_cache.py` (hash names, traversal-like keys, TTL)
- [ ] 1.3 Add the base class (state, subscribers on the GUI thread, placeholder, decoded LRU, background fetch) in `catalog/external_base.py`; verify with qtbot tests (placeholder then real image, callbacks on GUI thread)

## 2. Sources

- [ ] 2.1 Add category keyword data and `IconifySource` (+ Iconify and Phosphor defaults, search, batch assembly, licenses, glyph kind) with recorded fixtures; verify with `tests/test_external_iconify.py`
- [ ] 2.2 Add `GitHubRepoSource` (tree index, dedupe, raw URL, license, rate limit); verify with `tests/test_external_github.py`
- [ ] 2.3 Add `LocalFolderSource`; verify with `tests/test_external_local.py` (images, copied DLL, depth and file limits)
- [ ] 2.4 Add `build_external_sources`, reference parsing and local-folder helpers in `catalog/external.py`; verify with `tests/test_external_build.py`
- [ ] 2.5 Add offline behavior tests across sources and the `network` marker with optional live smoke tests; verify with `uv run pytest -q` (smoke skipped by default)

## 3. Wrap-up

- [ ] 3.1 Run `uv run ruff check`, `uv run ruff format --check`, `uv run pytest -q` and `openspec validate external-sources --strict`; all pass
