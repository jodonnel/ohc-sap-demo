# North/South Architecture Principle

## The Rule

**South is the edge. North is the intelligence.**

Every demo in this system follows one pattern:
- **South** generates events — edge devices, field simulations, sensors, vehicles, equipment, games, anything that represents the physical world
- **North** receives, aggregates, routes, and responds — integration with SAP BTP, SAP Edge Integration Cell, AI, dashboards, presentations

## What Belongs South

- Interactive device simulations (the Wumpus game, field scenarios)
- Vehicle telemetry relays (Mercedes, Smartcar)
- Equipment sensors (substation, shop floor, building systems)
- Wearable device feeds (Meta Ray-Ban glasses)
- Any future demo where a real or simulated physical device generates events

## What Belongs North

- Event ingestion API (/ingest)
- SSE stream (/events)
- State aggregation and persistence (Redis)
- Presentation decks and dashboards (static, served by nginx)
- SAP BTP integration endpoints
- SAP Edge Integration Cell relay

## Network Architecture

South devices talk to north via internal cluster DNS — never via public URLs hardcoded in client code.

```
Phone/Device (public internet)
    ↓
south route (TLS edge, public)
    ↓
south nginx
    ├── /* → south static files (device simulation UI)
    └── /ingest → proxy_pass http://north-nginx.qr-demo-qa.svc.cluster.local:8080/ingest
                        ↓
                   north-api (Flask + gunicorn)
                        ↓
                      Redis (persistent state)

Dashboard/Presentations (separate public route on north)
    ↓
north route (TLS edge, public)
    ↓
north-nginx
    ├── /dashboard.html, /present-*.html → static files (baked into image)
    └── /ingest, /events, /state, /health → proxy_pass north-api:5000
```

## Naming Convention

South services are named `south-*`. North services are named `north-*`. Routes follow the same pattern. This makes namespace topology self-documenting.

## Adding a New Demo

1. Build the device simulation/relay as a south component under `south-*/`
2. POST CloudEvents to relative `/ingest` (south nginx proxies to north internally)
3. North receives and aggregates — no north code changes required for new south sources
4. Add a presentation deck to `north/stage/` if the demo needs a slide deck

---
**Established:** 2026-02-21
**Author:** Jim O'Donnell + Chloe
