# Component Interaction

## The architecture

**North is decision support. South is execution. Both are permanent.**

- **North** — the enterprise integration surface. EIC, BTP, Analytics Cloud, AI Core. Everything that consumes events and turns them into business meaning. Decision support lives here. This boundary is permanent.
- **South** — device I/O. Badge readers, sensors, cameras, HVAC controllers. Everything that generates or acts on physical-world signals. Execution lives here. This boundary is permanent.
- **Middle** — the plumbing. Currently Flask on OpenShift. Could be Kafka, Event Mesh, a message bus, or something that doesn't exist yet. It normalizes and routes events between south and north. The middle is replaceable — north and south are not.

In the demo today, Flask plays the middle role: it ingests CloudEvents from south, aggregates telemetry, broadcasts via SSE, and surfaces signal through dashboards and presentations. When EIC arrives, it slots into north and the middle simplifies.

## Event flow

```
┌─────────────────┐      POST /ingest       ┌─────────────────────────────┐
│   South (edge)  │ ──────────────────────→  │        North (brain)        │
│                 │                          │                             │
│  south-ui/      │   CloudEvent v1.0        │  app.py                     │
│  index.html     │   {specversion, type,    │  ├─ count, telemetry, log   │
│                 │    source, id, time,     │  ├─ SSE broadcast           │
│  Badge taps     │    eventclass, data}     │  ├─ /data/state.json (PVC)  │
│  Sensor reads   │                          │  └─ all routes              │
│  Task actions   │                          │                             │
└─────────────────┘                          │  Consumers:                 │
                                             │  ├─ stage/dashboard.html    │
                                             │  ├─ stage/present*.html     │
                                             │  └─ stage/about.html        │
                                             └─────────────────────────────┘
```

## Components

### south-ui/index.html — "Confront the Wumpus"

The edge client. A mobile-first game where players badge through a 12-room building, complete compliance tasks, and confront a threat. Every action fires a CloudEvent to `POST /ingest`.

**Generates:**
- `access.onguard.badge_scan` — Lenel OnGuard badge events (grant/deny)
- `access.onguard.door_state` — door open/close/relock
- `maintenance.*`, `safety.*`, `surveillance.*` — task completion events
- `telemetry.device`, `telemetry.network`, `telemetry.battery` — passive device telemetry
- `sensor.environmental` — room temperature, humidity, air quality
- `game.complete`, `session.start` — game lifecycle

**Chloe layer:** Room-entry intel, task debriefs, proximity commentary, rotating tips.

### north/app.py — Flask event aggregator

The brain. Single Python process handling:

- **Ingestion** (`/ingest`) — accepts CloudEvents, increments counters, aggregates telemetry
- **SSE** (`/events`) — broadcasts events to all connected dashboard/presentation clients
- **State** (`/state`, `/telemetry`, `/log`) — JSON APIs for current state
- **Persistence** — flushes to `/data/state.json` every 10s, restores on startup
- **Evidence** (`/about`, `/about-panel`) — system metadata for credibility
- **Health** (`/healthz`, `/readyz`) — standard probes
- **Short URLs** (`/go/<alias>`) — redirect aliases for sharing

### stage/dashboard.html — Operations dashboard

North-side consumer. Connects to `/events` (SSE) and `/telemetry` (polling). Shows:

- Live event counter (hero number)
- Event feed (last N events, color-coded by class)
- Telemetry breakdowns (networks, locales, device classes)
- Event class distribution

### stage/present*.html — Presentations

Six audience-specific slide decks + a selector page. Each connects to SSE for a live event counter in the nav bar. The counter is the proof — "this number is going up because people in this room are generating events right now."

| File | Audience |
|------|----------|
| `present.html` | SAP sellers / customers |
| `present-rh.html` | Red Hat sellers (OHC + Partner comp) |
| `present-dtw.html` | Demo to Win (nervous system metaphor) |
| `present-util.html` | Utilities / energy vertical |
| `present-rail.html` | Rail / transport vertical |
| `present-ad.html` | Active Directory / identity vertical |

### stage/about.html — Evidence panel

Credibility anchor. Live-refreshing display of: version, commit, pod name, uptime, events processed, last event time, SSE client count. Linked from the gear icon in present-dtw nav bar.

## Deployment

Everything runs in one pod on OpenShift. HTML files are mounted via ConfigMaps:

| ConfigMap | Mount | Source |
|-----------|-------|--------|
| `north-app` | `/opt/app` | `north/app.py` |
| `north-stage-dashboard` | `/stage` | `north/stage/*` |
| `south-ui-html` | `/south-ui` | `south-ui/index.html` |
| `north-assets` | `/assets` | `north/assets/*` |

State persists on a 1Gi PVC mounted at `/data`.

## CloudEvent structure

Every event follows [CloudEvents v1.0](https://cloudevents.io/):

```json
{
  "specversion": "1.0",
  "type": "ohc.demo.access.onguard.badge_scan",
  "source": "south/lenel-reader-lobby",
  "id": "uuid",
  "time": "ISO-8601",
  "eventclass": "access",
  "data": { ... }
}
```

The `eventclass` field drives dashboard color-coding and breakdown aggregation:
- `access` — badge scans, door state
- `telem` — device telemetry, sensor readings
- `compliance` — maintenance, safety tasks
- `alert` — proximity warnings
- `status` — game lifecycle, door re-locks
- `sensor` — environmental readings
