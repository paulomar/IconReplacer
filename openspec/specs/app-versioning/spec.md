# app-versioning Specification

## Purpose
Defines how IconReplacer identifies its releases and iterations. It covers a four-part version with a never-resetting build counter, and how the version is shown to users.

## Requirements

### Requirement: Four-part version format
The application version SHALL have the form `MAJOR.MINOR.PATCH.BUILD`. Each part SHALL be a non-negative integer. One single source in the code base SHALL define the version, and every place that shows or embeds it SHALL read it from that source.

#### Scenario: Version string is well formed
- **WHEN** the application version is read
- **THEN** it matches the pattern `^\d+\.\d+\.\d+\.\d+$`

#### Scenario: Initial prototype version
- **WHEN** this change is merged into `main`
- **THEN** the application version is `0.1.0.1`

### Requirement: Monotonic build counter
BUILD SHALL increase by exactly one for every change merged into `main`, including bug-fix changes. BUILD SHALL never reset when MAJOR, MINOR or PATCH change. Each merge into `main` SHALL be tagged `vMAJOR.MINOR.PATCH.BUILD`.

#### Scenario: Build increments on merge
- **WHEN** a change is merged into `main` and the previous tag was `v0.1.0.1`
- **THEN** the new version has BUILD `2` and a tag `v<MAJOR>.<MINOR>.<PATCH>.2` exists

#### Scenario: Build does not reset on minor bump
- **WHEN** MINOR increases from `1` to `2` and the previous BUILD was `5`
- **THEN** the new BUILD is `6`

### Requirement: About dialog
The application SHALL provide an About dialog. It SHALL show:
- the product name;
- the version as `MAJOR.MINOR.PATCH` together with the build number;
- the license (MIT);
- a list of third-party components and their licenses;
- a notice that the icon converter and the system icon names and tags are part of IconReplacer, and that system icons are referenced in place;
- the notice "Third-party icon sources keep their own licenses".

#### Scenario: Open About
- **WHEN** the user opens About from the main window
- **THEN** a dialog shows "IconReplacer", the text `Version <MAJOR>.<MINOR>.<PATCH> (build <BUILD>)` matching the single version source, "MIT License", and a third-party notices section that lists at least PySide6/Qt with its license

#### Scenario: Icon data notices
- **WHEN** the user opens About
- **THEN** the notices mention the icon converter, the system icon data, and "Third-party icon sources keep their own licenses"

### Requirement: Version available from the command line
The application SHALL print its full four-part version and exit successfully when started with `--version`. It SHALL not open any window in that case.

#### Scenario: Print version
- **WHEN** the application is started with `--version`
- **THEN** it writes `IconReplacer <MAJOR>.<MINOR>.<PATCH>.<BUILD>` to standard output and exits with code 0 without showing a window
