## 1. Settings store

- [ ] 1.1 Implement `JsonSettingsStore` with typed defaults, validation, unknown-key preservation, atomic write and corrupt recovery. Verify: `uv run pytest tests/test_settings_store.py`

## 2. UI wiring

- [ ] 2.1 Create the store in `app.py` and restore/persist theme, sources visibility, geometry, thumbnail size, disabled sources and network switch. Verify: `uv run pytest tests/test_settings_ui.py`
- [ ] 2.2 Persist language and show the restart note; resolve empty language from the system locale. Verify: `uv run pytest tests/test_settings_ui.py`

## 3. Translations

- [ ] 3.1 Add `--release` to `tools/update_translations.py` and regenerate the English template. Verify: `uv run pytest tests/test_i18n.py`

## 4. Final checks

- [ ] 4.1 `uv run pytest -q`, `uv run ruff check`, `uv run ruff format --check`, `openspec validate settings-i18n --strict` all pass
