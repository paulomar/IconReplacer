# Proposal

## Why

When the user validated the 0.1.0.1 prototype, they found the default window too wide. The permanent source sidebar takes space that most users do not need, because the category chips already cover day-to-day filtering. Preview sizes above 64 px are not practical for judging folder icons.

## What Changes

- The source sidebar is **hidden by default**, and "All sources" is selected.
- A "Sources" toggle button sits in the search bar and shows or hides the sidebar:
  - Showing the sidebar widens the window by the panel width, but never past the available screen width and never while the window is maximized.
  - Hiding the sidebar shrinks the window by the same amount.
- While the sidebar is hidden and a specific source is selected, a removable "Source: <name>" indicator appears next to the search field. Removing it resets the source to All.
- The default window size becomes narrower: 1040x760.
- The preview shows only 16, 24, 32, 48 and 64 px, with 64 as the largest. The 128 and 256 previews are removed.
  - Generated icon files keep embedding the large sizes. Explorer's "Extra large icons" view uses them.
- Version: 0.1.1.2, a patch bump with build +1.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `icon-browser-ui`: The source navigation becomes a toggleable sidebar that is hidden by default, with an indicator for the active source. The preview sizes change to 16 to 64 px. The minimum-size scenario now refers to the sidebar only when it is shown.

## Impact

- `ui/main_window.py`, `ui/sidebar.py` and `ui/preview_panel.py`, plus a new small `ui/source_pill.py`. Tests and screenshots are updated.
- There is no change to the contracts, data or dependencies.
