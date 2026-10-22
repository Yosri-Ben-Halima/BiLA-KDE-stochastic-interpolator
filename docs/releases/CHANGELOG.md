# Change history

## Dashboard and research planning — 2026-10-22

### Added

- Campaign history dialog with archived outcomes, source/configuration identifiers,
  saved research narratives and linked validation stages. Recovery records stay attached
  to their original campaign; outcome aggregation excludes duplicate sources.
- Automatic discovery of saved run manifests, per-record evidence warnings and cached
  outcome counts. History remains local and read-only; a fresh checkout starts empty.
- Backend boundary/error tests and browser checks for history navigation, mobile layout,
  keyboard focus, empty history and recovery after a failed request.
- A documented next investigation comparing Python with one native kernel implementation
  at 4,000, 8,000 and 24,000 paths under a 60-minute experiment budget.

### Scope

The Python package remains at 0.1.0. This shipment changes the dashboard and documentation;
the statistical model, sampler and public Python API are unchanged. The native-kernel
investigation is planned; no implementation or new scientific experiment is included.
