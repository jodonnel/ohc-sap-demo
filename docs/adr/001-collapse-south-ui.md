# ADR-001: Consolidate south-ui serving into north pod

**Date:** 2026-02-16
**Status:** Accepted
**Deciders:** Jim O'Donnell, Chloe (architect), Claude Code, Claude Web

## Context

The demo has a core architectural metaphor: **north makes decisions, south operates.** South is the edge — badge taps, sensor readings, building operations. North is the brain — event aggregation, dashboards, presentations, evidence.

Originally this was two pods:

- **north** — Flask on UBI9: event ingestion, SSE, dashboard, presentations
- **south-ui** — Apache httpd on UBI8: served the wumpus game

In practice, north already served the game at `/play` via a ConfigMap mount. The south-ui pod was a duplicate serving the same HTML file through a separate Route.

## Decision

Remove the redundant south-ui pod, Service, and Route. North serves the game at `/play`. The `south-ui/` directory and `south-ui-html` ConfigMap remain — the code boundary is preserved.

**This is an infrastructure optimization, not an architectural change.** The north/south split is the value proposition. The event flow is still south→north:

```
Phone (south) → POST /ingest → Flask (north) → SSE → Dashboard (north)
```

The game doesn't know it's colocated. It posts to `/ingest` like any edge client.

## Consequences

- One pod to manage instead of two
- The north/south conceptual boundary is unchanged
- `south-ui/` remains a separate codebase with its own ConfigMap
- The demo narrative ("south operates, north decides") is unaffected
- If a future version needs true edge deployment (e.g., MicroShift), south-ui can be re-extracted trivially
