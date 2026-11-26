# Design

## Decisions

- **Hooks:** `app.extra_sources_factory` defaults to `real_extra_sources(settings)`. That function calls `catalog.external.build_external_sources(network_allowed=settings["network.allowed"])` without local folders, because `MainWindow` already restores `sources.local_folders` through `local_source_factory`. Passing local folders here as well would register duplicate source ids. `app.local_source_factory` defaults to `LocalFolderSource`. The hooks stay injectable, so tests keep using stubs or demo mode.
- **Shutdown:** when the app quits, `catalog.external.shutdown_all()` runs for the registry sources that support it. External workers are daemon threads, so nothing blocks process exit.
- **Application icon:** the drawing code moves from `packaging/make_app_icon.py` into `iconreplacer/ui/app_icon.py`, which provides `render(size) -> QImage` and `app_icon() -> QIcon`. The packaging script imports it, so the window icon and the exe icon cannot drift apart.

## Risks / Trade-offs

- [The default GitHub sources use the unauthenticated API, which allows 60 requests per hour] → The index is cached for 24 h, and an error state is shown when the limit is hit (already handled by the sources).
