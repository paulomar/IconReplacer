## ADDED Requirements

### Requirement: Restricted network access
All network access of external sources SHALL use HTTPS only, SHALL be limited to the hosts allowed for the requesting source, SHALL apply connect and read timeouts, SHALL reject responses larger than the per-request size limit, and SHALL identify itself with a generic user agent `IconReplacer/<version>` that carries no personal data. Redirects SHALL be followed only to allowed HTTPS hosts. When the network is not allowed, every request SHALL fail immediately without any connection attempt.

#### Scenario: Non-HTTPS URL
- **WHEN** a request is made to an `http://` URL
- **THEN** it fails with a typed error and no connection is made

#### Scenario: Host outside the allow-list
- **WHEN** a request targets a host that is not allowed for the source, or a redirect leads to one or to a non-HTTPS URL
- **THEN** the request fails with a typed error

#### Scenario: Oversized response
- **WHEN** a response is larger than the size limit
- **THEN** it is rejected with a typed error and nothing is cached

#### Scenario: Network disallowed
- **WHEN** the network is not allowed
- **THEN** every request fails immediately with an offline error and the transport is never called

### Requirement: Background loading with GUI-thread notification
External sources SHALL never block the caller: listing entries returns the currently known entries, and rendering an icon whose pixels are not yet available returns a neutral placeholder and schedules a fetch in the background. Subscribers SHALL be notified only on the GUI thread whenever the entries, the state or a thumbnail changes. Decoded images SHALL be kept in a bounded in-memory cache.

#### Scenario: Placeholder then real image
- **WHEN** an icon is rendered before its bytes have been downloaded
- **THEN** a transparent placeholder of the requested size is returned, and after the download completes a subscriber is notified and rendering returns the real image

#### Scenario: Callback thread
- **WHEN** a background fetch completes
- **THEN** every subscriber callback runs on the GUI thread

### Requirement: Failure backoff
After a failed fetch of an icon's image, the source SHALL NOT request that icon again until a backoff period has elapsed, starting at 30 seconds and doubling after each further failure up to 10 minutes. While backing off, rendering that icon SHALL return the placeholder without any request. At most one request per icon SHALL be in flight. The backoff SHALL be cleared by a success, a refresh, or a change of the network-allowed setting.

#### Scenario: Repeated rendering after a failure
- **WHEN** an icon fetch fails and the icon is rendered many times before the backoff expires
- **THEN** exactly one request has been made, and a new request is made only after the backoff has expired

#### Scenario: Backoff reset
- **WHEN** a refresh is requested or the network setting is toggled while an icon is backing off
- **THEN** the icon may be fetched again immediately

### Requirement: Fast shutdown
Sources and the module providing them SHALL offer a shutdown that cancels queued work and returns promptly without waiting for requests that are in flight. Background workers SHALL NOT keep the process alive. Results that arrive after a source was closed SHALL be dropped silently, without notifying subscribers.

#### Scenario: Shutdown during a blocked request
- **WHEN** shutdown is called while a network request is blocked
- **THEN** it returns in well under one second, and no subscriber is notified when the request finishes later

### Requirement: Disk cache
Downloaded files and indexes SHALL be cached under the application cache directory of the source. Cache file names SHALL be derived from a hash and never from remote paths. Indexes SHALL be considered fresh for 24 hours; a stale index SHALL be served immediately and refreshed in the background. When the network is not allowed, or a refresh fails, cached data SHALL be served.

#### Scenario: Hashed names
- **WHEN** a remote file named `../../evil.ico` is cached
- **THEN** the cache contains only a file whose name is a hexadecimal hash inside the source cache directory

#### Scenario: Offline with cache
- **WHEN** the network is not allowed and a cache exists
- **THEN** the source reports the offline state and still lists the cached entries and renders cached images

#### Scenario: Offline without cache
- **WHEN** the network is not allowed and no cache exists
- **THEN** the source reports the offline state and lists no entries

### Requirement: Iconify sources
IconReplacer SHALL provide an "Iconify" source with id `iconify` that searches across all Iconify collections, and a "Phosphor" source with id `phosphor` for the Phosphor collection. The default listing of Iconify SHALL be the result of the query "folder". The default listing of Phosphor SHALL contain only the regular weight, excluding names ending in `-thin`, `-light`, `-bold`, `-fill` and `-duotone`, and hidden icons. Icon images SHALL be fetched in batches and each entry SHALL carry the license of its collection. Entries of monochrome collections SHALL be of kind glyph, all others of kind full. Every entry SHALL have at least one canonical category.

#### Scenario: Default listings
- **WHEN** the sources load with a working network
- **THEN** Iconify lists the results for "folder" and Phosphor lists only regular-weight icons

#### Scenario: Search replaces entries
- **WHEN** a query is searched on an Iconify source
- **THEN** the entries are replaced by the results, and an empty query restores the default listing

#### Scenario: License and kind
- **WHEN** an entry of a collection with license MIT and no palette is listed
- **THEN** its license mentions MIT and its kind is glyph

### Requirement: GitHub repository sources
IconReplacer SHALL provide a source for each configured GitHub repository, by default `LaviMahal/WindowsIcons` and `sameerasw/folder-icons`. The source SHALL list the `.ico`, `.png`, `.svg` and `.icns` files of the repository below a size limit, keeping one entry per file stem with preference `.ico`, `.svg`, `.png`, `.icns`. Image bytes SHALL be fetched from `raw.githubusercontent.com` with a URL-encoded path. A repository without a declared license SHALL carry exactly the license text "No license declared - personal use at your own discretion". Rate limiting SHALL put the source in the error state with a readable message while cached data keeps being served.

#### Scenario: Deduplicate by stem
- **WHEN** a repository contains `ICO/blue.ico` and `PNG/blue.png`
- **THEN** one entry is listed and it references the `.ico` file

#### Scenario: Rate limit
- **WHEN** the repository index request is answered with HTTP 403 or 429 and a cached index exists
- **THEN** the state is error, the last error is readable, and cached entries are still listed

#### Scenario: Raw URL encoding
- **WHEN** the bytes of a file whose path contains spaces or special characters are fetched
- **THEN** the raw URL contains the percent-encoded path

### Requirement: Local folder source
IconReplacer SHALL provide a local folder source that scans a chosen folder in the background, recursively to a maximum depth of 4 and at most 5000 files, skipping hidden and system items and reparse points. Image files (`.ico`, `.png`, `.svg`, `.icns`) SHALL become file entries and icon libraries (`.dll`, `.exe`, `.icl`, `.mun`) SHALL yield one resource entry per icon group, referencing the absolute file path. The source SHALL not depend on the network and SHALL be ready after the scan.

#### Scenario: Images and libraries
- **WHEN** a folder with an image and a DLL that contains icons is scanned
- **THEN** the source lists a file entry for the image and resource entries for the DLL icons, and its state is ready

#### Scenario: Limits
- **WHEN** a folder tree is deeper than 4 levels or holds more than 5000 matching files
- **THEN** items below the depth limit are ignored and no more than 5000 files are examined

### Requirement: External source construction
IconReplacer SHALL build the default external sources with `iconify` and `phosphor` ids, one `gh-<owner>-<repo>` source per configured repository and one `local-<hash>` source per local folder. Repository references SHALL be accepted only as `owner/repo` or a `https://github.com/owner/repo` URL matching a strict pattern; anything else SHALL be rejected.

#### Scenario: Reference parsing
- **WHEN** `https://github.com/LaviMahal/WindowsIcons.git` or `LaviMahal/WindowsIcons` is parsed
- **THEN** the owner and repository are returned, and values such as `a/b/c`, `../x` or `http://evil.test/a/b` are rejected
