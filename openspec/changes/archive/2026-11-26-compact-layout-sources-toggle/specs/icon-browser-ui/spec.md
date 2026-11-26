# Spec Delta

## MODIFIED Requirements

### Requirement: Resizable main window
The main window SHALL be freely resizable and SHALL support maximizing. Its minimum size SHALL be no larger than 800x560 logical pixels. When the window is resized, the icon grid SHALL reflow to use the available width.

#### Scenario: Grid reflows on resize
- **WHEN** the user widens the window
- **THEN** the icon grid shows more columns without horizontal scrolling

#### Scenario: Minimum size
- **WHEN** the user shrinks the window to its minimum size
- **THEN** all primary controls (search, grid, preview, actions, and the sources sidebar when shown) remain reachable

### Requirement: Source and category navigation
A sidebar SHALL group icon sources into the sections "System libraries", "Online sources" and "Local folders". Each system library entry SHALL show its library name, a short description and an icon count. Selecting an entry SHALL limit the grid to that source. An "All" entry SHALL show every source. The sidebar SHALL be hidden when the window first opens, and "All" SHALL be selected.

#### Scenario: Filter by library
- **WHEN** the user shows the sidebar and selects "imageres.dll"
- **THEN** the grid shows only icons whose source is imageres.dll and the count shown matches the number of grid items

#### Scenario: System library list
- **WHEN** the user shows the sidebar
- **THEN** the "System libraries" section lists at least imageres.dll, shell32.dll, ddores.dll, wmploc.dll, mmres.dll, netshell.dll, networkexplorer.dll, pnidui.dll, wpdshext.dll, wiashext.dll, setupapi.dll, dmdskres.dll, dsuiext.dll, accessibilitycpl.dll, sensorscpl.dll, powercpl.dll, mstscax.dll, ieframe.dll, mmcndmgr.dll, compstui.dll, pifmgr.dll and moricons.dll

#### Scenario: Hidden by default
- **WHEN** the main window opens
- **THEN** the sources sidebar is not visible, "All" is the selected source, and the grid shows icons from every available source

### Requirement: Icon preview
Selecting an icon SHALL show a preview panel with:
- the icon at 16, 24, 32, 48 and 64 pixels, with 64 being the largest size shown;
- its source and resource identifier;
- its categories;
- its license.

The panel SHALL offer a "Compose on folder base" toggle and a tint color picker. Both SHALL update the preview immediately.

#### Scenario: Preview sizes
- **WHEN** the user selects an icon
- **THEN** the preview panel shows that icon at each of the sizes 16, 24, 32, 48 and 64, and at no size larger than 64, together with its source, identifier, categories and license

#### Scenario: Compose on folder base
- **WHEN** the user enables "Compose on folder base" and picks a tint color
- **THEN** every preview size shows the glyph drawn over a folder shape filled with the chosen tint

## ADDED Requirements

### Requirement: Sources sidebar toggle
A "Sources" toggle control SHALL show and hide the sources sidebar. When the window is not maximized, showing the sidebar SHALL widen the window by the sidebar width, up to the available screen width. Hiding the sidebar SHALL narrow the window by the same amount. When the window is maximized, its size SHALL not change.

#### Scenario: Show sources widens the window
- **WHEN** the window is 1040 px wide, not maximized, the screen has room, and the user activates "Sources"
- **THEN** the sidebar becomes visible, the window becomes wider by the sidebar width, and the grid keeps at least its previous width

#### Scenario: Hide sources restores the width
- **WHEN** the user deactivates "Sources" after showing it
- **THEN** the sidebar is hidden and the window returns to its previous width

#### Scenario: Maximized window
- **WHEN** the window is maximized and the user toggles "Sources"
- **THEN** the window stays maximized and only the internal layout changes

### Requirement: Active source indicator
While the sidebar is hidden and a source other than "All" is selected, the window SHALL show a "Source: <name>" indicator next to the search field. Dismissing the indicator SHALL reset the source to "All". The indicator SHALL be hidden whenever "All" is selected or the sidebar is visible.

#### Scenario: Indicator after hiding sidebar
- **WHEN** the user selects "shell32.dll" in the sidebar and then hides the sidebar
- **THEN** a "Source: shell32.dll" indicator is visible and the grid is still filtered to shell32.dll

#### Scenario: Dismiss indicator
- **WHEN** the user dismisses the "Source: shell32.dll" indicator
- **THEN** the source becomes "All", the grid shows every available source, and the indicator disappears
