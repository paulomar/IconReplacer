# app-storage-locations Specification

## Purpose
Defines where IconReplacer stores settings, caches and logs. Portable installs keep everything next to the application, and other installs use the user's local application data.

## Requirements

### Requirement: Portable storage next to the application
When the directory that contains the application is writable, IconReplacer SHALL store its data in a `data` subdirectory of that directory. In that layout, settings and logs SHALL go in `data`, and caches SHALL go in `data\cache`.

#### Scenario: Writable application directory
- **WHEN** the application runs from a writable directory `D:\Tools\IconReplacer`
- **THEN** settings are stored under `D:\Tools\IconReplacer\data` and caches under `D:\Tools\IconReplacer\data\cache`

### Requirement: Fallback to local application data
When the application directory is not writable, IconReplacer SHALL store its data under `%LOCALAPPDATA%\IconReplacer`, using the same `cache` subdirectory layout.

#### Scenario: Read-only application directory
- **WHEN** the application directory cannot be written
- **THEN** settings are stored under `%LOCALAPPDATA%\IconReplacer` and caches under `%LOCALAPPDATA%\IconReplacer\cache`

### Requirement: Explicit home override
When the `ICONREPLACER_HOME` environment variable is set to a directory path, IconReplacer SHALL use that directory as its data root, with the same layout, and SHALL ignore both other locations.

#### Scenario: Override
- **WHEN** `ICONREPLACER_HOME` is `C:\Temp\ir-home`
- **THEN** settings are stored under `C:\Temp\ir-home` and caches under `C:\Temp\ir-home\cache`

### Requirement: Directories created on demand
IconReplacer SHALL create its storage directories the first time it needs them. It SHALL NOT create any directory outside the selected data root.

#### Scenario: First run
- **WHEN** the application needs to write settings and the data root does not exist
- **THEN** the data root is created and no other directory on the system is created
