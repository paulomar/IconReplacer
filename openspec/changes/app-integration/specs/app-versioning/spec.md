## MODIFIED Requirements

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
