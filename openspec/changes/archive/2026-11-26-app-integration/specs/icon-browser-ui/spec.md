## MODIFIED Requirements

### Requirement: Folder actions
The window SHALL offer Apply, Undo and Restore default actions for the target folders, and they SHALL really change the folders through the folder icon service. Actions SHALL run without blocking the window: while one runs, a busy indicator SHALL be shown and the action buttons and target selection SHALL be disabled. On completion a notification SHALL state how many folders succeeded.

#### Scenario: Apply to one folder
- **WHEN** the user selects a system icon and clicks Apply with one target folder
- **THEN** the folder's desktop.ini references that icon and a notification states the icon was applied to 1 folder

#### Scenario: Simulated apply
- **WHEN** the application runs in demo mode (`ICONREPLACER_DEMO=1`) and the user selects an icon and clicks Apply with one or more targets
- **THEN** a notification states the icon was applied in simulation, and no file or registry entry on the system is created or changed

#### Scenario: Busy while running
- **WHEN** an action is running
- **THEN** a busy indicator is visible and Apply, Undo, Restore default and "Choose folders…" are disabled until it finishes

#### Scenario: Undo and restore
- **WHEN** the user clicks Undo after an apply, or Restore default
- **THEN** the folder returns to its previous state, or to the default icon, and a notification reports the folder count

### Requirement: Settings view
The application SHALL provide a Settings view containing:
- a list of icon sources that can be enabled or disabled, plus a control to add a local folder source when a local folder source provider is available;
- a "Allow network access" switch;
- a language selector;
- a theme selector with System, Light and Dark;
- an "Explorer integration" group.

#### Scenario: Network kill switch visible
- **WHEN** the user opens Settings
- **THEN** an "Allow network access" switch is present and the online sources are shown as unavailable while it is off

#### Scenario: No local folder provider
- **WHEN** the application has no local folder source provider
- **THEN** the "Add local folder…" control is not shown

## ADDED Requirements

### Requirement: Batch confirmation
Before running Apply, Undo or Restore default on more than one folder, the window SHALL ask for confirmation and list the target folders. Declining SHALL leave every folder unchanged.

#### Scenario: Declined batch
- **WHEN** the user clicks Apply with three target folders and declines the confirmation
- **THEN** no folder is changed and no action runs

#### Scenario: Single folder
- **WHEN** the user clicks Apply with one target folder
- **THEN** no confirmation is asked

### Requirement: Failure details
When an action fails for any folder, the window SHALL show a details dialog listing each failed folder with its reason. Known reasons SHALL be shown through the translation layer; unknown reasons SHALL be shown as reported.

#### Scenario: Protected folder in a batch
- **WHEN** an icon is applied to a valid folder and a protected folder
- **THEN** the valid folder is changed, the notification reports 1 of 2 folders, and the details dialog lists the protected folder with the reason "System and program folders are protected."

### Requirement: Choose target folders
The target header SHALL offer a "Choose folders…" control that opens a folder picker. Each picked folder SHALL be added to the targets unless it is already listed, so several folders can be chosen by picking repeatedly.

#### Scenario: Start without arguments
- **WHEN** the application is started without `--folder` and the user picks two folders one after another
- **THEN** the header shows "2 folders" and Apply becomes available once an icon is selected

#### Scenario: Duplicate pick
- **WHEN** the user picks a folder that is already a target
- **THEN** the target list is unchanged

### Requirement: Real catalog by default
The window SHALL list the real Windows system icon libraries and any additional sources supplied by the application. Generated demo sources and simulated actions SHALL only be used when the `ICONREPLACER_DEMO` environment variable is `1`.

#### Scenario: Normal start
- **WHEN** the application starts without `ICONREPLACER_DEMO`
- **THEN** the system libraries come from the Windows installation and actions modify folders

#### Scenario: Demo mode
- **WHEN** the application starts with `ICONREPLACER_DEMO=1`
- **THEN** generated demo sources are shown and actions are simulated

### Requirement: Dynamic source status
For sources whose content arrives asynchronously, the window SHALL update the grid, the sidebar counts and the thumbnails whenever such a source reports a change. The sidebar SHALL show a state badge "Loading…", "Offline" or "Error" while the source is not ready, with the last error as tooltip for "Error". The network switch SHALL be forwarded to every such source, and an enabled source SHALL be asked to load when the window opens and when network access is turned on.

#### Scenario: Source finishes loading
- **WHEN** a dynamic source reports new entries
- **THEN** the grid and the sidebar count include them without restarting

#### Scenario: Network switched off
- **WHEN** the user turns network access off
- **THEN** every dynamic source is told that network access is disallowed

#### Scenario: Error badge
- **WHEN** a dynamic source is in the error state
- **THEN** its sidebar entry shows "Error" and its tooltip contains the source's last error

### Requirement: Remote search
When the selected source in the sidebar supports remote search, typing in the search field SHALL send the query to that source after 400 ms without further typing, and its results SHALL not be filtered again by the local text match. With "All" or a non-searchable source selected, only local filtering SHALL apply. Leaving a searched source SHALL restore its default listing.

#### Scenario: Debounced query
- **WHEN** a searchable source is selected and the user types "arrow" quickly
- **THEN** the source receives exactly one query "arrow" about 400 ms after the last keystroke

#### Scenario: All sources
- **WHEN** "All" is selected and the user types a search term
- **THEN** no source receives a remote query and the grid is filtered locally
