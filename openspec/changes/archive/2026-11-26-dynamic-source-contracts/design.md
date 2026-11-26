# Design

## Decisions

- **`SourceState`** has four values: `READY`, `LOADING`, `OFFLINE` (network disallowed or unreachable) and `ERROR`.
- **`DynamicIconSource`** extends `IconSource` with these members:
  - `state() -> SourceState`;
  - `last_error() -> str | None`;
  - `subscribe(callback) -> unsubscribe`. Callbacks are always invoked on the Qt GUI thread whenever `entries()`, the state or the rendered thumbnails change;
  - `refresh()`, which is non-blocking;
  - `set_network_allowed(bool)`.

  `entries()` returns what is currently known and never blocks. `render()` never blocks either: when the pixels are not available yet, it returns a placeholder image and schedules a fetch that notifies the subscribers once the pixels arrive.
- **`SearchableIconSource`** has `search(query: str) -> None`. The search is non-blocking, and its results replace `entries()` before subscribers are notified. An empty query restores the default listing.
- **`IconBytesProvider`** has `fetch_bytes(entry) -> bytes`. It **may block**, so it is only called from a worker thread at apply time, never during painting. It raises `OSError` or `ValueError` on failure.
- **Callbacks as plain callables:** using Qt signals in the Protocol would force every implementation to be a `QObject`. Implementations still use Qt signals internally to marshal results onto the GUI thread.

## Risks / Trade-offs

- [The contract may turn out too small once it meets real sources] → Members can be extended later with defaults. Implementers report gaps instead of working around them.
