# Proposal

## Why

Every building block is now on `main`: system DLL sources, online/GitHub/local sources, the converter, the real folder service, settings, Explorer integration and packaging. The application still starts with system libraries only, because the integration hooks for external sources were left empty on purpose. The window also has no icon of its own. This change connects the pieces and produces the 1.0 release.

## What Changes

- The app catalog includes the external sources by default:
  - Iconify;
  - Phosphor;
  - the GitHub repositories `LaviMahal/WindowsIcons` and `sameerasw/folder-icons`.

  The network switch in Settings governs them.
- "Add local folder…" creates real local folder sources. They are restored at the next start.
- Background network work is shut down quickly when the app quits.
- The original application icon is drawn by a module inside the package. It is used for the window and taskbar and by the packaging icon generator, so there is one design in one place.
- Version 1.0.0.13. A release zip is built, smoke-tested and checksummed.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `icon-browser-ui`: "Real catalog by default" now includes the online and GitHub sources and real local folder sources.

## Impact

- Code: `app.py`, a new `ui/app_icon.py`, `packaging/make_app_icon.py`, and related tests.
- Release: `dist/IconReplacer-1.0.0.13-win64.zip`.
