# Tasks

## 1. Sources sidebar toggle and indicator

- [x] 1.1 Add the "Sources" toggle (Ctrl+B), hide the sidebar by default with All selected, and add the width-preserving window resize with screen clamping; verify with pytest-qt that the sidebar is hidden on open, that showing it widens the window, that hiding it restores the width, and that a maximized window keeps its state
- [x] 1.2 Add `ui/source_pill.py` and wire it to the sidebar's visibility and selected source; verify with tests that the indicator appears after selecting shell32.dll and hiding the sidebar, and that dismissing it resets to All
- [x] 1.3 Set the default window size to 1040x760 and adjust the splitter defaults; verify that the minimum-size test still passes with the sidebar shown and hidden

## 2. Preview sizes

- [x] 2.1 Limit the preview to 16, 24, 32, 48 and 64 with 64 as the hero, and reduce the panel's minimum width; verify with tests that exactly these sizes are rendered and that none is larger than 64

## 3. Release

- [x] 3.1 Run `ruff check`, `ruff format --check`, `pytest` and `update_translations.py`; verify that all are clean
- [x] 3.2 Update `tools/screenshots.py` (default, sources shown, indicator) and the README, regenerate the screenshots, and review them visually; verify that the files exist and that there is no layout defect
- [x] 3.3 Bump the version to 0.1.1.2, archive the change, commit, merge into main, tag v0.1.1.2 and delete the branch; verify with `git tag` and `uv run iconreplacer --version`
