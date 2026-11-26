# icon-browser-ui Specification

## Purpose
Defines the main IconReplacer window, a modern, resizable, technical icon picker for folders. It lets users browse icons by source and category, search, preview and choose an icon for one or more target folders.

## Requirements

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

### Requirement: Category filtering
Every icon SHALL carry one or more categories, for example Folders, Drives & Storage, Devices, Media, Network, Security, System, Users, Accessibility, Power or Legacy. The user SHALL be able to filter the grid by category, and this filter SHALL combine with the source filter.

#### Scenario: Combine source and category
- **WHEN** the user selects source "shell32.dll" and category "Folders"
- **THEN** the grid shows only icons that are from shell32.dll and tagged Folders

### Requirement: Search
A search field SHALL filter the grid as the user types. Matching SHALL be case-insensitive and SHALL check the icon name, its tags and its resource identifier. When no icon matches, the grid area SHALL show an explicit empty state.

#### Scenario: Search by tag
- **WHEN** the user types "network" in the search field
- **THEN** the grid shows only icons whose name, tags or identifier contain "network" (case-insensitive)

#### Scenario: No results
- **WHEN** the search matches no icon
- **THEN** the grid area shows a "No icons match" message instead of an empty grid

### Requirement: Adjustable thumbnail size
The user SHALL be able to change the grid thumbnail size continuously between 16 and 256 pixels. The chosen size SHALL apply to every grid item.

#### Scenario: Change thumbnail size
- **WHEN** the user moves the size slider to 96
- **THEN** grid thumbnails are rendered at 96x96 pixels

### Requirement: Grid scales to large catalogs
The grid SHALL stay responsive when it holds at least 10,000 icons. Scrolling and filtering SHALL not block the UI noticeably.

#### Scenario: Large mock catalog
- **WHEN** the grid is populated with 10,000 mock icons and the user types a search term
- **THEN** the filtered result appears within 300 ms on a typical developer machine

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

### Requirement: Target folders header
The window SHALL show the folder or folders that the icon will be applied to. These come from command-line `--folder <path>` arguments, and each argument can be repeated. With several targets, the header SHALL show the count and allow the full list to be expanded. With no target, the header SHALL say so and the apply action SHALL be disabled.

#### Scenario: Batch targets
- **WHEN** the application is started with `--folder C:\A --folder C:\B --folder C:\C`
- **THEN** the header shows "3 folders" and expanding it lists the three paths

#### Scenario: No target
- **WHEN** the application is started without `--folder`
- **THEN** the header shows "No target folder" and Apply is disabled

### Requirement: Folder actions
The window SHALL offer Apply, Undo and Restore default actions for the target folders. In this prototype the actions SHALL be simulated. They SHALL report what would happen, and they SHALL NOT modify any file, folder attribute or registry key.

#### Scenario: Simulated apply
- **WHEN** the user selects an icon and clicks Apply with one or more targets
- **THEN** a notification states the icon would be applied to the targets, and no file or registry entry on the system is created or changed

### Requirement: Settings view
The application SHALL provide a Settings view containing:
- a list of icon sources that can be enabled or disabled, plus a control to add a local folder source;
- a "Allow network access" switch;
- a language selector;
- a theme selector with System, Light and Dark.

#### Scenario: Network kill switch visible
- **WHEN** the user opens Settings
- **THEN** an "Allow network access" switch is present and the online sources are shown as unavailable while it is off

### Requirement: Theme follows system
By default the application SHALL use a light or dark appearance that matches the Windows app theme. The user SHALL be able to override it with Light or Dark, and the change SHALL take effect without restarting.

#### Scenario: Override theme
- **WHEN** the user selects Dark in Settings while Windows uses the light theme
- **THEN** the window switches to the dark appearance immediately

### Requirement: Translatable user interface
Every user-visible string SHALL go through the application's translation layer. English SHALL be the default and only shipped language. The language list in Settings SHALL be built from the translations that are available. The selected language SHALL be persisted and SHALL take effect on the next start; when it is changed, Settings SHALL show a note that IconReplacer must be restarted to apply it. When no language is selected, the system language SHALL be used if a matching translation exists, otherwise English.

#### Scenario: Strings are translatable
- **WHEN** the translation extraction tool runs over the source
- **THEN** every user-visible string of the main window, Settings and About appears in the generated translation template

#### Scenario: Language change shows restart note
- **WHEN** the user picks another language in Settings
- **THEN** the choice is persisted and a note "Restart IconReplacer to apply the language" is shown

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
