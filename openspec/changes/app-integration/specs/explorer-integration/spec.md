## ADDED Requirements

### Requirement: Registration management in Settings
Settings SHALL show the registration status as "Not registered", "Registered" or "Stale – points to another location" (with the registered path), and SHALL offer Register (or Re-register when a registration exists) and Unregister. It SHALL note that Windows 11 shows the entry under "Show more options". A failed operation SHALL show its error and SHALL NOT crash.

#### Scenario: Register from Settings
- **WHEN** the status is Not registered and the user clicks Register
- **THEN** the verb is registered and the status shows "Registered"

#### Scenario: Unregister from Settings
- **WHEN** the status is Registered and the user clicks Unregister
- **THEN** the verb is removed and the status shows "Not registered"

### Requirement: Stale registration banner
When the registration status is Stale at startup, the main window SHALL show a non-blocking banner offering "Fix Explorer integration". Using it SHALL re-register the verb for the current launcher and hide the banner.

#### Scenario: Portable app moved
- **WHEN** the window opens and the registered command points to another launcher
- **THEN** a banner offers "Fix Explorer integration", and clicking it makes the status Registered

#### Scenario: Registered or absent
- **WHEN** the window opens and the status is Registered or Not registered
- **THEN** no Explorer integration banner is shown
