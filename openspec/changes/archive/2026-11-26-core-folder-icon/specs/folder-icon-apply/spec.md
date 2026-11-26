# Spec Delta

## Purpose

Defines how IconReplacer applies, undoes and resets custom folder icons on Windows. The rules keep user folders safe, keep the icon working when a folder moves, and make every change reversible.

## ADDED Requirements

### Requirement: Apply a resource icon
When the chosen icon resolves to an icon resource inside a DLL or EXE, the system SHALL set `IconResource=<location>,-<resource_id>` in the `[.ShellClassInfo]` section of the folder's `desktop.ini`. It SHALL keep environment-variable references in the location unexpanded.

#### Scenario: System DLL icon
- **WHEN** an icon with location `%SystemRoot%\System32\shell32.dll` and resource id 4 is applied to a folder
- **THEN** the folder's desktop.ini contains `IconResource=%SystemRoot%\System32\shell32.dll,-4` under `[.ShellClassInfo]`

### Requirement: Apply a generated ICO icon portably
When the chosen icon resolves to ICO data, the system SHALL store the data atomically as `.iconreplacer\icon-<h>.ico` inside the target folder, where `<h>` is the first 12 hex digits of the data's SHA-256. It SHALL reference that file with the relative path `.iconreplacer\icon-<h>.ico,0` and SHALL delete stored `icon-*.ico` files that are no longer referenced. It SHALL mark the `.iconreplacer` directory Hidden and System.

#### Scenario: ICO payload
- **WHEN** ICO data is applied to a folder
- **THEN** `<folder>\.iconreplacer\icon-<h>.ico` contains exactly that data and desktop.ini contains `IconResource=.iconreplacer\icon-<h>.ico,0`

#### Scenario: Re-applying a different ICO changes the referenced file name
- **WHEN** different ICO data is applied to a folder that already has a stored icon
- **THEN** desktop.ini references a new `icon-<h>.ico` name and the previous icon file is removed

#### Scenario: Folder moved
- **WHEN** a folder with an applied ICO icon is moved to another location
- **THEN** its desktop.ini still references the icon by the relative path and needs no change

### Requirement: Explorer-compatible attributes
After applying an icon, the system SHALL mark desktop.ini Hidden and System and SHALL set the ReadOnly attribute on the folder so that Explorer honours the customization.

#### Scenario: Attributes after apply
- **WHEN** an icon is applied to a folder that had no desktop.ini
- **THEN** desktop.ini has the Hidden and System attributes and the folder has the ReadOnly attribute

### Requirement: Preserve unrelated desktop.ini content
When the system changes icon keys, it SHALL keep all other sections, keys and values of an existing desktop.ini. It SHALL keep the file's encoding unless the new content needs non-ASCII characters, in which case it SHALL write UTF-16 LE with a byte order mark.

#### Scenario: Existing localized name and view state
- **WHEN** an icon is applied to a folder whose desktop.ini contains `LocalizedResourceName` and a `[ViewState]` section
- **THEN** both are still present with unchanged values after the apply

### Requirement: Undo restores the exact previous state
Before every change, the system SHALL record the folder's previous state: the desktop.ini bytes or their absence, the desktop.ini and folder attributes, and the names and bytes of the stored icon files. It SHALL keep this record in `.iconreplacer\history.json`, bounded to the 10 most recent changes. Undo SHALL restore the most recent record exactly and remove it.

#### Scenario: Undo after first apply
- **WHEN** an icon is applied to a folder and then undone
- **THEN** desktop.ini bytes, folder attributes and desktop.ini attributes are identical to before the apply and no `.iconreplacer` directory remains

#### Scenario: Undo of a second apply
- **WHEN** two icons are applied in turn and the change is undone once
- **THEN** the folder shows the first icon again, with the same desktop.ini bytes and the same stored icon file name and bytes as after the first apply

#### Scenario: Nothing to undo
- **WHEN** undo is requested on a folder without history
- **THEN** that folder is reported as failed with a reason and nothing is changed

### Requirement: Restore the default icon
Restoring the default SHALL remove only the `IconResource`, `IconFile` and `IconIndex` keys from `[.ShellClassInfo]` and SHALL delete desktop.ini when no keys remain. It SHALL remove the `.iconreplacer` directory and SHALL clear the folder's ReadOnly or System attribute only when IconReplacer set that attribute.

#### Scenario: Restore after apply on a clean folder
- **WHEN** an icon was applied to a folder without desktop.ini and the default is restored
- **THEN** no desktop.ini and no `.iconreplacer` directory remain and the folder no longer has the ReadOnly attribute

#### Scenario: Restore keeps other customizations
- **WHEN** the default is restored on a folder whose desktop.ini also contains `LocalizedResourceName`
- **THEN** desktop.ini remains with `LocalizedResourceName` and without any icon key

### Requirement: Refuse unsafe targets
The system SHALL resolve each target path, removing `..` segments and short names, before checking it. It SHALL refuse, with a clear reason and without changing anything, a target that does not exist or is not a directory, a drive or share root, a folder equal to or under the Windows, Program Files or ProgramData folders, the user profile root itself, a symlink or junction (on the target or an ancestor), or a folder it cannot write to. UNC paths and user profile subfolders SHALL be allowed.

#### Scenario: Drive root
- **WHEN** `C:\` is a target
- **THEN** it is refused with a reason that mentions the drive root

#### Scenario: System folder through a dot-dot path
- **WHEN** the target is `<Windows folder>\..\<Windows folder name>\Temp`
- **THEN** it is refused as a system folder

#### Scenario: Profile root and subfolder
- **WHEN** the user profile root and one of its subfolders are targets
- **THEN** the profile root is refused and the subfolder is accepted

#### Scenario: Junction
- **WHEN** the target is a directory junction
- **THEN** it is refused as a link

### Requirement: Batch operations report per folder
For several target folders, the system SHALL process each folder independently and SHALL continue after a failure. The result SHALL succeed only when every folder succeeded, SHALL list the folders that succeeded, and SHALL name each failed folder with its reason in a short English message.

#### Scenario: One refused folder
- **WHEN** an icon is applied to two valid folders and one drive root
- **THEN** both valid folders get the icon, the result is not successful, the two valid folders are the affected ones, and the message names the refused folder and its reason

### Requirement: Repeated apply is idempotent
Applying the same icon again to a folder SHALL leave desktop.ini and the stored icon with the same content as after the first apply.

#### Scenario: Apply twice
- **WHEN** the same icon is applied twice to a folder
- **THEN** desktop.ini contains a single `IconResource` line, its bytes equal those after the first apply, and the stored icon keeps the same file name

### Requirement: No elevation and Explorer refresh
The system SHALL never request elevation and SHALL never modify the registry, restart Explorer or clear the icon cache. After each folder change it SHALL notify the shell that the folder was updated.

#### Scenario: Notification
- **WHEN** an icon is applied to, undone on or reset on a folder
- **THEN** the shell is notified of the update for that folder path
