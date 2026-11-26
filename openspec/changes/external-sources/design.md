## Context

See proposal.md. Contracts (`DynamicIconSource`, `SearchableIconSource`, `IconBytesProvider`,
`SourceState`) already exist in `core/`. Images are decoded through `converter.load_image`,
which validates SVG/raster input. Another change wires the UI to these sources.

## Goals / Non-Goals

**Goals:** non-blocking sources; hardened network access; offline-first caching; no network in the default test run.

**Non-Goals:** UI, settings persistence, applying icons, authentication (GitHub token), pagination of huge repositories (truncated trees are used as returned).

## Decisions

- **Transport**: `net.HttpClient` wraps a `Transport` callable (`(url, headers, timeout, max_bytes) -> Response`). The default transport uses `urllib` with a redirect handler that re-validates scheme and host; tests inject a fake. Redirect and host rules live in the client, not the transport, so fakes are checked too. Alternative: `requests` (new dependency) rejected.
- **Threading**: a shared `Worker` hub built on `concurrent.futures.ThreadPoolExecutor`; completed work is marshalled to the GUI thread with a `QObject` signal (queued connection, object living in the GUI thread, created lazily from the GUI thread). Subscribers are called only from that slot. Alternative QThreadPool needs QRunnable boilerplate with no benefit.
- **Base class** `ExternalSourceBase` holds state, last error, subscribers, decoded LRU, placeholder, fetch dedup (in-flight set), the network flag and `fetch_bytes` caching; subclasses provide `_load_index()` (blocking, worker thread) and `_url_for(entry)`/`_hosts`.
- **Disk cache** (`online_cache.DiskCache`): files `<sha256>.bin` and `<sha256>.json` under `cache_dir(source_id)`, written atomically (temp + replace). Index records carry a `fetched_at` timestamp; fresh < 24 h. Stale or OFFLINE: serve cached immediately, refresh only when allowed.
- **State machine**: READY after a successful index; LOADING while loading with no entries or refreshing; OFFLINE when the network is disallowed or unreachable; ERROR for rate limits/HTTP/parse failures. Cached entries are always served in any state.
- **Iconify**: collection metadata from `/collections?prefixes=...` (cached) gives license and palette; search results already embed collection metadata. SVG bodies are fetched with `/{prefix}.json?icons=a,b,c` in batches of 40 names; each batch is split into standalone SVGs (width/height/viewBox from the JSON with default 16 per the Iconify data format, and `currentColor` replaced by the loader) stored in the disk cache per icon. Rendering schedules the batch for all visible-requested icons of that prefix (requests are coalesced by a short batching window of pending names).
- **Categories**: `external_data/category_keywords.json` maps keywords to canonical categories and Iconify collection categories/tags to defaults; fallback category is `System` (neutral, always valid), documented in the data file.
- **GitHub**: index via the Git trees API (default branch resolved from `/repos/{o}/{r}`; a `main`/`master` fallback is not guessed). License comes from the repo API `license.spdx_id` when present; otherwise the fixed "No license declared - personal use at your own discretion". Dedup by lowercase stem within the same directory-agnostic scope (stem plus top category path) is not used: sameerasw has `ICO/x.ico` and `PNG/x.png`, so dedup is by stem across the repo with extension preference.
- **Local source**: a scan thread using `os.scandir` with depth/file limits, skipping `FILE_ATTRIBUTE_HIDDEN|SYSTEM|REPARSE_POINT`; DLL groups via `pe_icons.PeModule` (one library failing is ignored). Rendering decodes on demand through the worker.
- **No path-derived cache names / ids**: entry ids use `<source-id>:<sha1(location)[:16]>` (+ resource id).

## Risks / Trade-offs

- [Iconify/GitHub API change or outage] -> typed errors, ERROR state, cache served.
- [GitHub unauthenticated rate limit 60/h] -> 24 h index cache and stale-while-revalidate; readable message.
- [Malicious remote SVG/PNG] -> all decoding via `converter.load_image` validation; size limits in the client.
- [Qt objects used from threads] -> workers only handle bytes; QImage decoding happens in the GUI thread (placeholder until then) except SVG rasterization that is cheap.

## Open Questions

None blocking.
