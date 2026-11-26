# Design

## Context

See proposal.md for motivation. The pieces already exist behind the `core.contracts`
protocols: `SystemIconSource` (thread-safe, `RLock` around its PE module), the converter
(`ConverterMaterializer`, `convert_to_ico`, `compose_ico`), `WindowsFolderIconService(materializer)`
and `ShellRegistration(backend)`. Online, GitHub and local-folder sources are built concurrently in
`catalog/` by another change and implement `DynamicIconSource`, `SearchableIconSource` and
`IconBytesProvider`. This change must not import them and must not change `core/`.

## Goals / Non-Goals

**Goals:** real end-to-end apply/undo/restore from the UI; a generic integration point for the
coming sources; registration management from the UI; tests that stay fast and side-effect free
(R0/R1).

**Non-Goals:** concrete online/GitHub/local sources; asynchronous loading of the system catalog
(first start enumerates libraries synchronously, later starts use the index cache); showing the
folder's actual current icon in the header.

## Decisions

### Materializer routed per source
`CompositeMaterializer(registry)` looks up `registry.get(entry.source_id)` and delegates to a
`ConverterMaterializer` built for that source: `render_provider=source.render` and
`bytes_provider=source.fetch_bytes` when the source is an `IconBytesProvider`. Otherwise the
bytes provider raises `ConversionError("… cannot provide image data")`. Unknown sources raise
`ConversionError` too. The service turns every materializer exception into the failed result
"The icon could not be prepared: …", so no folder is touched.
*Alternative:* a new materializer per call in the UI. Rejected: the service owns the materializer
by contract.

### App wiring and injection points
`create_window(options, app, settings, *, registry=None, service=None, registration=None,
extra_sources_factory=None, local_source_factory=None)`. Defaults come from module-level hooks
in `app.py`: `extra_sources_factory(settings) -> list[IconSource]` (returns `[]`) and
`local_source_factory: Callable[[Path], IconSource] | None = None`. A later small change points
them at the external sources factory. `ICONREPLACER_DEMO=1` swaps in `build_mock_sources()`, the
`MockFolderIconService`, a mock local factory and an in-memory registration backend, so tests and
screenshots never touch folders or the registry. `run()` keeps the single-instance and settings
logic unchanged.

### Worker thread for actions
`services/apply_worker.py` holds `ActionRunner(QObject)` with a private `QThreadPool` limited to
one thread, so actions are serialized. Each job is a `QRunnable` calling the service; the result
(or an exception converted to a failed `ActionResult`) is emitted through a `Signal`, therefore
delivered on the GUI thread. The window shows an indeterminate progress bar in the header and
disables actions and target selection while `runner.busy`. On close the window waits for the
pool. Rendering for composition happens in the worker; `SystemIconSource` is lock-protected and
`QImage`/`QPainter` on images are safe off the GUI thread.

### Per-folder failure details without contract change
`ActionResult` carries only `ok`, `message` and `affected`. Failed folders are the targets whose
resolved path is not in `affected`; their reasons are parsed from the service's message
(`"… Failed: <name>: <reason>; <name>: <reason>"`) by locating each failed folder's
`"<name>: "` prefix in order. When parsing fails, the whole message is used. Fixed English reasons
are translated through a `QT_TRANSLATE_NOOP("Reasons", …)` table; unknown text (OS errors) is
shown verbatim. *Alternative:* structured failures in `ActionResult` — rejected, `core/` is
read-only for this change.

### Dynamic sources
At construction the window subscribes to every `DynamicIconSource` in the registry and forwards
the network switch with `set_network_allowed`. After the window is built (and whenever network
access is turned on or a source is re-enabled) enabled dynamic sources get `refresh()`.
Subscriber callbacks only mark the source dirty and start a 50 ms single-shot timer; the timer
compares entry ids, rebuilds the grid model only when they changed (preserving the selected entry
by id), clears the thumbnail cache and repaints, re-renders the preview when its entry belongs to
the source, and updates sidebar counts and state badges. Unsubscribe on close.

### Remote search scope
Remote queries go only to the source selected in the sidebar, when it is a
`SearchableIconSource` and available. "All" never triggers remote queries, to avoid fanning out
a request to every online provider on every keystroke. A 400 ms single-shot timer debounces the
text. The proxy exempts that source's entries from the local text match (its results already
match the query). Leaving the source, or clearing the text, sends `search("")` once to restore its
default listing.

### Explorer integration UI
`SettingsView` takes an optional `ShellRegistration`. The group shows status text, a primary
button whose text is Register or Re-register, Unregister, and the Windows 11 hint. Operations
catch `OSError` and show the error. The main window checks the status once at startup; a Stale
status shows the banner with a "Fix Explorer integration" button that calls `register()` and
refreshes the Settings group. Tests use a fake backend.

### Banner
The banner gains an optional action button and an optional timeout (0 = stays). Success
messages auto-hide after 8 s; the stale banner and failure banners stay until replaced or
closed.

## Risks / Trade-offs

- [Parsing the service message for reasons is brittle] → fallback to the full message; the
  format is covered by tests in this change and in the service tests.
- [First start enumerates ~25 libraries synchronously] → the index cache makes later starts
  fast; asynchronous loading is a later improvement.
- [Composition in a worker while the grid renders on the GUI thread] → `SystemIconSource` locks
  its PE module; dynamic sources must already be thread-safe for `fetch_bytes` per contract.
- [Real folder writes from the UI] → the service refuses unsafe targets, backs up state and
  offers undo; batches need confirmation.
