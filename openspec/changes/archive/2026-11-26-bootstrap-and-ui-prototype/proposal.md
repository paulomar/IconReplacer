# Proposal

## Why

Windows' built-in "Change Icon" dialog shows a small, fixed, decades-old grid from `shell32.dll`. It is not resizable and has no categories or search. IconReplacer replaces it with a modern, technical, resizable picker for power users. This first change sets up the project foundation and builds a clickable visual prototype. The user validates the look and feel before any real folder-modifying logic is written.

## What Changes

- Rename the default branch `master` to `main` to match the project's Git policy.
- Create the Python project scaffold:
  - `uv`-managed, Python 3.14, `src/iconreplacer` package layout;
  - pytest and ruff for tests and linting;
  - MIT `LICENSE`, a `.gitignore` for Python, and a `README.md`.
- Add a single source of truth for the application version in `MAJOR.MINOR.PATCH.BUILD` form:
  - this change ships `0.1.0.1`;
  - BUILD is a counter that never resets and increases by one for every change merged into `main`.
- Add an **About** dialog that shows the name, version and build, license, and third-party notices.
- Record the project's durable constraints in the `context` block of `openspec/config.yaml`, so that every later change inherits them:
  - English artifacts;
  - portability;
  - security and risk levels R0 to R3;
  - no GPL dependencies;
  - the versioning rule.
- Build a clickable, resizable PySide6 **UI prototype** that uses mock data only. It contains:
  - a source and category sidebar;
  - a virtualized icon grid with search, filter and a size slider;
  - a preview panel at 16 to 256 px, with a folder-base composition toggle and a tint picker;
  - a header that lists the target folder or folders, including batch mode;
  - mocked Apply / Undo / Restore default actions;
  - a Settings view with sources, a network kill switch, language and theme;
  - light and dark themes that follow the system;
  - every UI string passing through the translation layer.
- The prototype never modifies the filesystem or registry.
- This change ends with a pause: screenshots and the running prototype go to the user for visual validation.

## Capabilities

### New Capabilities
- `app-versioning`: application version format, build counter semantics, and how the version is shown to the user (About).
- `icon-browser-ui`: the main icon-picking window — layout, navigation by source/category, search/filter, preview, target-folder display, actions, settings view, theming and translatability.

### Modified Capabilities
<!-- none: no existing specs -->

## Impact

- New code under `src/iconreplacer/` (app entry point, UI, mock catalog, version module), and tests under `tests/`.
- New dependencies: PySide6 (LGPL) as the runtime dependency; pytest, pytest-qt and ruff as development dependencies. All are installed into the project-local `.venv`.
- Git: the default branch becomes `main`, and work for this change happens on `feat/bootstrap-and-ui-prototype`.
- No system side effects. Nothing is written outside the repository and `.venv`.
- Follow-up changes: `core-folder-icon`, `system-dll-source`, `icon-converter`, `settings-i18n`, `external-sources`, `catalog-ui`, `shell-integration`, `packaging`. They replace the mock data and mocked actions with real behavior.
