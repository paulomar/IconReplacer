# app-settings Specification

## Purpose
TBD - created by archiving change settings-i18n. Update Purpose after archive.

## Requirements

### Requirement: Persistent settings file
User settings SHALL be stored in a JSON file named `settings.json` in the data root, with a schema version and a values map. Settings SHALL be saved whenever a value changes and when the application exits. Writes SHALL be atomic so that a failure never leaves a partially written file.

#### Scenario: Round trip
- **WHEN** a setting is changed and the settings are loaded again from the same file
- **THEN** the changed value is returned

#### Scenario: Failed write keeps the previous file
- **WHEN** saving fails midway
- **THEN** the previously saved `settings.json` is unchanged and still valid

### Requirement: Typed defaults and validation
Each known setting SHALL have a default and a validator. The known settings are: network allowed (default on), theme (system, light or dark; default system), language (code; default empty meaning follow the system), sources panel visible (default off), window geometry (default none), thumbnail size (16 to 256; default 48), disabled sources (list of ids) and local folders (list of absolute paths). An invalid stored value SHALL be replaced by the default and a warning SHALL be logged. Unknown keys SHALL be preserved when saving.

#### Scenario: Invalid value falls back
- **WHEN** the file holds a thumbnail size of 9999 or a theme of "purple"
- **THEN** the default is used and a warning is logged

#### Scenario: Unknown keys survive
- **WHEN** the file contains a key this version does not know and a setting is changed
- **THEN** the unknown key is still present in the saved file

### Requirement: Corrupt file recovery
When `settings.json` cannot be read or parsed, the application SHALL rename it to `settings.json.corrupt-<timestamp>`, start with defaults and SHALL NOT crash.

#### Scenario: Corrupt file
- **WHEN** `settings.json` contains invalid JSON at startup
- **THEN** the file is renamed with the corrupt suffix and the application starts with default settings

### Requirement: Settings restored in the UI
At startup the application SHALL restore the theme, sources panel visibility, thumbnail size, disabled sources, network switch and window geometry. Window geometry SHALL be applied only when it fits a currently connected screen; otherwise the default size is used. These values SHALL be saved when they change and when the window closes.

#### Scenario: Preferences survive a restart
- **WHEN** the user sets the dark theme, shows the sources panel and sets the thumbnail size to 96, then the window is recreated from the same settings
- **THEN** the new window uses the dark theme, shows the sources panel and has a thumbnail size of 96

#### Scenario: Off-screen geometry ignored
- **WHEN** the stored window geometry lies outside every connected screen
- **THEN** the window opens with its default size and position
