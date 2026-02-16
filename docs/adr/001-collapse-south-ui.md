# ADR-001: Consolidate south-ui serving into north pod

**Date:** 2026-02-16
**Status:** Accepted
**Deciders:** Jim O'Donnell, Chloe (architect), Claude Code, Claude Web

## Context

The demo has a three-layer architecture:

- **South** (execution) — device I/O. Badge readers, sensors, cameras. Permanent boundary.
- **Middle** (plumbing) — event ingestion, normalization, routing. Replaceable.
- **North** (decision support) — dashboards, presentations, evidence. EIC/BTP when available. Permanent boundary.

Originally the south layer ran as a separate pod (Apache httpd on UBI8) serving the wumpus game. North ran Flask on UBI9 handling everything else. In practice, north already served the game at `/play` via a ConfigMap mount. The south-ui pod was a duplicate serving the same HTML file through a separate Route.

## Decision

Remove the redundant south-ui pod, Service, and Route. The middle layer (Flask) serves the game at `/play`. The `south-ui/` directory and `south-ui-html` ConfigMap remain — the code boundary is preserved.

**This is an infrastructure optimization, not an architectural change.** The south/north boundary is permanent. The event flow is unchanged:

```
South (execution) → POST /ingest → Middle (Flask) → SSE → North (dashboards)
```

The game doesn't know it's colocated. It posts to `/ingest` like any edge client.

## Consequences

- One pod to manage instead of two
- The south/north architectural boundary is unchanged
- `south-ui/` remains a separate codebase with its own ConfigMap
- The demo narrative ("south executes, north supports decisions") is unaffected
- If a future version needs true edge deployment (e.g., MicroShift), south-ui can be re-extracted trivially
- The middle layer (Flask) is still replaceable — EIC/Kafka can slot in without touching south or north
