# system-icon-library Specification

## Purpose
Defines how IconReplacer discovers, classifies, renders and exports the icons that Windows ships in its system libraries. Icons are always referenced in place by resource ID and are never redistributed.

## Requirements

### Requirement: One source per Windows icon library
IconReplacer SHALL provide one system icon source for each of these files:
- the libraries imageres.dll, shell32.dll, ddores.dll, wmploc.dll, mmres.dll, netshell.dll, networkexplorer.dll, pnidui.dll, wpdshext.dll, wiashext.dll, setupapi.dll, dmdskres.dll, dsuiext.dll, accessibilitycpl.dll, sensorscpl.dll, powercpl.dll, mstscax.dll, ieframe.dll, mmcndmgr.dll, compstui.dll, pifmgr.dll and moricons.dll;
- the companion files powrprof.dll, mstsc.exe and shdocvw.dll.

Each source SHALL be identified by its file name and SHALL carry a short description.

#### Scenario: Available libraries
- **WHEN** the system sources are built on Windows 11
- **THEN** one source exists for each listed file that is present in `%SystemRoot%\System32`, and its name is the file name

#### Scenario: Missing library
- **WHEN** a listed file does not exist on the running Windows build
- **THEN** no error is raised, and either that library is left out of the built sources or its source reports zero icons

### Requirement: Icons referenced in place by resource ID
Each icon entry SHALL reference its library as `%SystemRoot%\System32\<file>` together with a positive integer resource ID. The entry SHALL be an icon group of that library that has an integer ID. Icon groups identified by a string name SHALL be left out. Within one library, the IDs SHALL be unique. Every entry SHALL carry the license text "Microsoft Windows (referenced in place, not redistributed)". No icon image data SHALL be copied into the application or its repository.

#### Scenario: Reference format
- **WHEN** the entries of imageres.dll are listed
- **THEN** every entry references `%SystemRoot%\System32\imageres.dll` with a positive resource ID that is unique within the library

#### Scenario: String-named groups
- **WHEN** a library contains icon groups that have string names
- **THEN** those groups do not appear as entries

### Requirement: Icons stored in Windows resource files
When a library's icons are stored in its companion resource file under `%SystemRoot%\SystemResources`, the source SHALL still list and render those icons. The entries SHALL keep referencing the System32 path of the library.

#### Scenario: Icons moved to SystemResources
- **WHEN** the System32 copy of imageres.dll is a small stub and its icons live in `imageres.dll.mun`
- **THEN** the imageres.dll source lists those icons and still references `%SystemRoot%\System32\imageres.dll`

### Requirement: Rendering at any size
A system icon SHALL render as a square image of exactly the requested pixel size. Rendering SHALL use the image in the icon group that best fits the requested size, in this order:
1. an image whose size equals the requested size;
2. otherwise, the nearest larger image, scaled down smoothly;
3. otherwise, the largest image, scaled up.

Rendering SHALL support both PNG-compressed images and classic bitmap images.

#### Scenario: Common sizes
- **WHEN** an imageres.dll icon is rendered at 16, 32, 48, 64 and 256 pixels
- **THEN** each image is non-null and exactly that size

#### Scenario: Non-standard size
- **WHEN** an icon is rendered at a size that the icon group does not contain
- **THEN** the image has the requested size and is produced from the nearest larger image when one exists

### Requirement: Export as an ICO file
IconReplacer SHALL be able to produce standalone `.ico` file content for any system icon entry. That content SHALL contain every image of the icon group.

#### Scenario: Export
- **WHEN** a shell32.dll icon is exported
- **THEN** the bytes start with the ICO header and decode as an image

### Requirement: Classification into categories
Every system icon entry SHALL carry at least one category, and all of its categories SHALL come from the canonical category list. IconReplacer SHALL classify entries as follows:
- Well-known icons of imageres.dll and shell32.dll SHALL take their name, categories and tags from a curated mapping, for example folders, drives, users, network, security, devices, documents and media.
- Every other icon SHALL take its library's default categories and be named `<library> #<id>`.

The tags of every entry SHALL include the library name and the resource ID.

#### Scenario: Curated icon
- **WHEN** the entries of imageres.dll are listed
- **THEN** each icon from the curated mapping has the curated name and categories, and its tags include `imageres.dll` and its ID

#### Scenario: Uncurated icon
- **WHEN** an icon of ddores.dll has no curated data
- **THEN** it is named `ddores.dll #<id>` and its category is Devices

### Requirement: Fast, cached enumeration
A system source SHALL NOT read its library until its entries are requested for the first time. After that first read, the source SHALL store its library index in the application cache directory. The cache key SHALL be based on the library file's path, size and modification time. A later session SHALL reuse that index without enumerating the library again, as long as those values are unchanged. Listing the entries of imageres.dll SHALL take less than 1.5 seconds without the cache and less than 100 milliseconds with it.

#### Scenario: Warm start
- **WHEN** imageres.dll entries are listed in a new session and a valid cached index exists
- **THEN** the same entries are returned as without the cache, in less than 100 milliseconds

#### Scenario: Library updated
- **WHEN** the size or modification time of the library file changes
- **THEN** the cached index is ignored and rebuilt

### Requirement: Read-only system access
System sources SHALL open library files only as read-only resource data. They SHALL NOT execute code from them. They SHALL NOT write anywhere except the application cache directory. They SHALL NOT need elevation.

#### Scenario: Standard user
- **WHEN** a standard, non-elevated user lists and renders system icons
- **THEN** it works, and the only files written are inside the application cache directory
