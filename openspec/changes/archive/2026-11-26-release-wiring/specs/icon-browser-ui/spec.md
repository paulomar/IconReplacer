# Spec Delta

## MODIFIED Requirements

### Requirement: Real catalog by default
The window SHALL list the real Windows system icon libraries, the online sources (Iconify and Phosphor), the default GitHub repository sources and the user's local folder sources. Generated demo sources and simulated actions SHALL only be used when the `ICONREPLACER_DEMO` environment variable is `1`.

#### Scenario: Normal start
- **WHEN** the application starts without `ICONREPLACER_DEMO`
- **THEN** the system libraries come from the Windows installation, the sidebar lists Iconify, Phosphor, LaviMahal/WindowsIcons and sameerasw/folder-icons, and actions modify folders

#### Scenario: Demo mode
- **WHEN** the application starts with `ICONREPLACER_DEMO=1`
- **THEN** generated demo sources are shown and actions are simulated

#### Scenario: Local folders restored
- **WHEN** the user added a local folder in a previous session
- **THEN** that folder appears again as a local source after restart

## ADDED Requirements

### Requirement: Application icon
The application window SHALL use the IconReplacer application icon, and the executable SHALL embed the same design.

#### Scenario: Window icon
- **WHEN** the main window is shown
- **THEN** its window icon is the IconReplacer icon and is not empty

### Requirement: Prompt shutdown
Quitting the application SHALL NOT wait for network requests in progress.

#### Scenario: Quit while downloading
- **WHEN** the user closes the window while an online source is still downloading
- **THEN** the process exits without waiting for the download to finish
