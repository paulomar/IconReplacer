# Proposal

## Why

Wave 2 runs `external-sources` (Iconify/Phosphor, GitHub repositories, local folders) in parallel with `app-integration` (wiring the real services into the UI). Online sources load asynchronously and depend on the network. Both sides need one shared contract for that, and they need it before they start.

## What Changes

- Add internal protocols to `core/contracts.py`:
  - `DynamicIconSource`: has a state, can subscribe to changes, can refresh, and follows the network kill switch.
  - `SearchableIconSource`: runs remote queries.
  - `IconBytesProvider`: provides the raw image bytes used to build `.ico` files at apply time.
- Add a `SourceState` enum to `core/models.py`.
- No user-visible behaviour changes, so this change declares `skip_specs: true`.
- Version 0.6.1.9.

## Capabilities

### New Capabilities
<!-- none: internal contracts only -->

### Modified Capabilities
<!-- none -->

## Impact

`core/contracts.py`, `core/models.py`, and new tests. Nothing else.
