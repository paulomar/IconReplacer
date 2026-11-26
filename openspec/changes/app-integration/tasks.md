# Tasks

## 1. Materializer

- [ ] 1.1 `services/materializer.py` `CompositeMaterializer(registry)` routing resource / composed resource / bytes-provider entries with typed `ConversionError`s (verify: `tests/test_integration_materializer.py` covers resource, compose, stub bytes provider, missing provider, unknown source)

## 2. App wiring

- [ ] 2.1 `app.py`: real system sources + `extra_sources_factory` hook, `WindowsFolderIconService(CompositeMaterializer)`, `local_source_factory` hook, injectable registry/service/registration, demo mode via `ICONREPLACER_DEMO=1`; `run()` unchanged otherwise (verify: test that demo and normal wiring pick the expected service/sources; existing settings UI tests pass in demo mode)
- [ ] 2.2 Hide "Add local folder…" when no local factory; restore persisted local folders through the factory (verify: settings UI test)

## 3. Real actions

- [ ] 3.1 `services/apply_worker.py` `ActionRunner` (single-thread pool, GUI-thread result signal) and busy state in the header (verify: busy test)
- [ ] 3.2 Real Apply/Undo/Restore in `MainWindow` with banner success count, batch confirmation, failure details dialog with translated reasons (verify: end-to-end tests on `tmp_path` folders with the real service, batch decline/accept, protected folder via env var)
- [ ] 3.3 "Choose folders…" button with de-duplication (verify: test with monkeypatched `QFileDialog`)

## 4. Dynamic and searchable sources

- [ ] 4.1 Subscribe/unsubscribe, coalesced refresh of grid, counts, thumbnails and preview; sidebar state badges with error tooltip (verify: stub dynamic source test)
- [ ] 4.2 Network switch forwards `set_network_allowed` and refreshes enabled sources (verify: stub test)
- [ ] 4.3 Debounced remote search on the selected searchable source, local-filter exemption, restore on leave (verify: debounce test)

## 5. Explorer integration UI

- [ ] 5.1 Settings "Explorer integration" group with status and Register / Re-register / Unregister (verify: fake backend test)
- [ ] 5.2 Stale banner with "Fix Explorer integration" at startup (verify: fake backend stale test)

## 6. About, i18n, docs

- [ ] 6.1 About notices for converter/system data and the third-party source license caveat (verify: About test)
- [ ] 6.2 Regenerate `iconreplacer_en.ts` and extend i18n checks for new strings (verify: `test_i18n.py`)
- [ ] 6.3 `tools/screenshots.py` with real system icons, non-existent demo targets and the simulated service; regenerate and review `docs/screenshots` (verify: images reviewed, no folder written)
- [ ] 6.4 README: status, Explorer menu registration (`--register` or Settings) (verify: read through)

## 7. Integration

- [ ] 7.1 `uv run pytest -q`, `uv run ruff check`, `uv run ruff format --check`, `openspec validate app-integration --strict` all pass
