## ADDED Requirements

### Requirement: Per-user folder context-menu verb
The system SHALL register a static "Replace Icon" verb for folders under `HKCU\Software\Classes\Directory\shell\IconReplacer` only, with `MUIVerb` and default value "Replace Icon", `Icon` set to the executable path, and a `command` subkey whose default value is `"<launcher>" --folder "%1"` with every path correctly quoted. The system SHALL NOT write any other registry key, require elevation, or restart Explorer.

#### Scenario: Register in a frozen build
- **WHEN** registration is requested and the app runs as a frozen executable
- **THEN** the command value is `"<exe path>" --folder "%1"` and `Icon` is the exe path

#### Scenario: Register in development
- **WHEN** registration is requested from a development environment
- **THEN** the command launches the virtualenv `pythonw.exe` with `-m iconreplacer --folder "%1"` and paths containing spaces are quoted

#### Scenario: Registration is idempotent
- **WHEN** registration is requested while already registered
- **THEN** the values are overwritten with the current ones and no error occurs

### Requirement: Registration status and removal
The system SHALL report one of NotRegistered, Registered, or Stale (the verb exists but its command points to another or missing launcher) and SHALL remove only its own key tree on unregister.

#### Scenario: Stale after moving the portable app
- **WHEN** the registered command points to a launcher path different from the current one or to a missing file
- **THEN** status is Stale and exposes the registered path so the UI can offer re-registration

#### Scenario: Unregister removes only our key
- **WHEN** unregistration is requested
- **THEN** `IconReplacer` and its `command` subkey are deleted, sibling keys are untouched, and unregistering when absent succeeds

### Requirement: Command-line management flags
The CLI SHALL provide `--register`, `--unregister` and `--status` that print a result, never open a window, and exit 0 on success and 1 on failure (for `--status`, 0 when Registered and 1 otherwise).

#### Scenario: Status of an unregistered app
- **WHEN** `--status` runs and the key is absent
- **THEN** it prints "not registered" and exits with code 1

#### Scenario: Existing flags preserved
- **WHEN** `--folder PATH` or `--version` is used
- **THEN** behaviour is unchanged

### Requirement: Single-instance folder aggregation
The system SHALL let the first instance own a per-user local server; later instances SHALL send their `--folder` arguments to it and exit with code 0, and the first instance SHALL merge folders arriving during a short startup window and append later arrivals. If the server cannot be reached the instance SHALL start normally.

#### Scenario: Multi-select merges into one window
- **WHEN** Explorer launches three instances in quick succession for three folders
- **THEN** exactly one window opens with all three folders, de-duplicated

#### Scenario: Server unreachable
- **WHEN** a client cannot connect to the server
- **THEN** it becomes the first instance and starts normally

### Requirement: Safe IPC
The server SHALL accept only length-prefixed JSON messages up to 64 KB containing absolute paths of existing directories, SHALL reject malformed, oversized or invalid messages without side effects, and SHALL never execute received data. The server name SHALL be derived from the current user and application name.

#### Scenario: Malformed message
- **WHEN** a client sends invalid JSON, a non-list payload, or an oversized length
- **THEN** the message is ignored and no folders are added

#### Scenario: Invalid path
- **WHEN** a message contains relative or non-existent paths
- **THEN** those entries are dropped and valid ones are kept
