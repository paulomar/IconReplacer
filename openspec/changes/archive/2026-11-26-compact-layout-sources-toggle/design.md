# Design

## Context

See proposal.md. This change builds on the 0.1.0.1 prototype, where the main window used a three-pane `QSplitter` (sidebar | grid | preview).

## Goals / Non-Goals

**Goals:** a compact default layout, a predictable resize when toggling the sidebar, and no hidden filter state.

**Non-Goals:** persisting whether the sidebar is shown (that belongs to `settings-i18n`), and changing the grid's thumbnail range (16 to 256 stays).

## Decisions

- **Toggle:** a checkable `QToolButton` labelled "Sources", placed at the left of the search bar, with the shortcut Ctrl+B. The sidebar stays in the splitter and only its visibility changes. **Alternative considered:** a dock widget. It was rejected because docking and floating add complexity this tool does not need.
- **Window resize:** when the window is not maximized or full screen, the window width changes by the sidebar width, which is remembered between toggles and starts at 250 px. Growth is clamped to the screen's available geometry. If the window had to be clamped, it shrinks back by the delta it actually grew, so repeated toggles never drift.
- **Indicator:** a small `SourcePill` widget (a label plus a close button). `MainWindow` updates it from two inputs: whether the sidebar is visible, and which source is selected. Closing it selects "All" in the sidebar.
- **Preview:** sizes are 16, 24, 32, 48 and 64. The 64 px image is the hero, centred, and the other sizes sit in a row below it. The panel's minimum width drops to about 240 px.
- **Version:** `tools/bump_version.py patch` gives 0.1.1.2.

## Risks / Trade-offs

- [The window manager may refuse a resize, for example when the window is snapped] → Compute the delta from the actual geometry after the resize; the tests cover the unmaximized and maximized cases.
- [Users may not notice the toggle] → The button has a visible text label, and the indicator guarantees the filter is never invisible.
