# Tasks

## 1. Storage locations

- [x] 1.1 Implement `core/paths.py` (`app_dir`, `data_root`, `settings_path`, `cache_dir`, `log_dir`, `reset_cache`) with the override, portable and LOCALAPPDATA rules; verify with tests using monkeypatched env and a read-only simulation that each rule selects the right root and that directories are only created on demand

## 2. Contracts

- [x] 2.1 Add `IconPayload` (with validating constructors) to `core/models.py` and the `IconMaterializer` Protocol to `core/contracts.py`; verify with tests that invalid payloads are rejected and that a stub materializer satisfies the protocol
- [x] 2.2 Git-ignore `.worktrees/` and `data/`; verify with `git check-ignore`

## 3. Release

- [x] 3.1 Run ruff and pytest; bump to 0.1.2.3; archive; merge and tag; verify with `git tag`
