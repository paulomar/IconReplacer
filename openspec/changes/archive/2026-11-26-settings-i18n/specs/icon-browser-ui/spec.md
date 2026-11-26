## MODIFIED Requirements

### Requirement: Translatable user interface
Every user-visible string SHALL go through the application's translation layer. English SHALL be the default and only shipped language. The language list in Settings SHALL be built from the translations that are available. The selected language SHALL be persisted and SHALL take effect on the next start; when it is changed, Settings SHALL show a note that IconReplacer must be restarted to apply it. When no language is selected, the system language SHALL be used if a matching translation exists, otherwise English.

#### Scenario: Strings are translatable
- **WHEN** the translation extraction tool runs over the source
- **THEN** every user-visible string of the main window, Settings and About appears in the generated translation template

#### Scenario: Language change shows restart note
- **WHEN** the user picks another language in Settings
- **THEN** the choice is persisted and a note "Restart IconReplacer to apply the language" is shown
