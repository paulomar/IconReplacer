## 1. Registration

- [ ] 1.1 `shell/registration.py` with backend protocol, fake-friendly API, `status()/register()/unregister()` (verify: fake-backend unit tests)
- [ ] 1.2 Command quoting and launcher detection (verify: spaces test)

## 2. Single instance

- [ ] 2.1 `shell/ipc.py` server/client with validation and size cap (verify: in-process QLocalServer tests)
- [ ] 2.2 Startup aggregation window (verify: merge test)

## 3. CLI and app hook

- [ ] 3.1 `--register/--unregister/--status` without Qt GUI import (verify: CLI tests)
- [ ] 3.2 Minimal `app.py` hook (verify: full suite passes)

## 4. Verification

- [ ] 4.1 Real-registry R1 test with verified rollback (verify: `reg query` shows key absent afterwards)
- [ ] 4.2 `uv run pytest -q`, `uv run ruff check`, `uv run ruff format --check`
