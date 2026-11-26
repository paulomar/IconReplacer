## ADDED Requirements

### Requirement: Icon resolved through its source
The system SHALL turn the chosen icon into what is written by asking the icon's own source. A resource icon SHALL be referenced in place unless composition on the folder base is requested; then it SHALL be composed from the source's rendered pixels into ICO data. Any other icon SHALL be converted to ICO data from the raw image bytes its source provides. When the source is unknown or cannot provide what is needed, the action SHALL fail with a clear reason and no folder SHALL be changed.

#### Scenario: System icon as-is
- **WHEN** a shell32.dll icon is applied without composition
- **THEN** the folder references `%SystemRoot%\System32\shell32.dll` with the icon's resource id

#### Scenario: System icon composed
- **WHEN** a system icon is applied with "Compose on folder base"
- **THEN** a generated ICO file is stored in the folder and referenced

#### Scenario: Downloaded icon
- **WHEN** an icon from a source that provides raw SVG or PNG bytes is applied
- **THEN** the bytes are converted and a generated ICO file is stored in the folder and referenced

#### Scenario: Source without bytes
- **WHEN** a non-resource icon comes from a source that cannot provide raw bytes
- **THEN** the action fails with a reason stating the icon cannot be prepared and no folder is changed
