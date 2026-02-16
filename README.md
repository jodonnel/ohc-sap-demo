# OHC Edge Demo — Red Hat x SAP

Live interactive demo: physical security events flowing from edge devices through Red Hat OpenShift to SAP BTP via Edge Integration Cell.

## Screenshots

<p align="center">
  <img src="docs/img/wumpus-game.png" alt="Wumpus mobile game" width="220">
</p>

## Architecture

```
Phone (edge) → POST /ingest → Flask on OpenShift → SSE → Dashboard / Presentations
                                    ↓
                              /data/state.json (PVC — survives pod restarts)
```

Single pod (`north`) serves everything: event ingestion, SSE broadcast, game, dashboard, presentations, evidence panel. No separate web server — just Flask on UBI9.

[View the animated architecture diagram](https://jodonnel.github.io/ohc-sap-demo/architecture.html)

## Endpoints

| Path | Description |
|------|-------------|
| `/play` | Mobile wumpus game (Lenel OnGuard badge events + Chloe guide) |
| `/stage` | Operations dashboard (event counter, telemetry, breakdowns) |
| `/present` | SAP seller presentation (10 slides, live SSE counter) |
| `/present-rh` | Red Hat seller presentation (OHC + Partner comp) |
| `/present-dtw` | Demo to Win presentation (nervous system metaphor) |
| `/present-util` | Utilities/Energy vertical presentation |
| `/present-rail` | Rail/Transport vertical presentation |
| `/present-ad` | Active Directory / identity vertical presentation |
| `/present-index` | Presentation selector |
| `/about-panel` | System evidence panel (uptime, commit, SSE clients) |
| `/ingest` | POST endpoint for CloudEvents |
| `/events` | Server-Sent Events stream |
| `/state` | Current state JSON |
| `/telemetry` | Aggregated device telemetry |
| `/log` | Event history (last 200) |
| `/about` | System metadata JSON |
| `/healthz` | Liveness probe |
| `/readyz` | Readiness probe |
| `/go/<alias>` | Short URL redirects (`/go/play`, `/go/dtw`, `/go/stage`, etc.) |
| `/go` | List all short URLs |
| `/reset` | POST — reset all state |

## Running locally

```bash
cd north/
pip install flask
python app.py
# Game:          http://localhost:8080/play
# Dashboard:     http://localhost:8080/stage
# Presentation:  http://localhost:8080/present
# Send event:    curl -X POST http://localhost:8080/ingest \
#                  -H 'Content-Type: application/json' \
#                  -d '{"type":"ohc.demo.test","data":{"ping":true}}'
```

**Deploy to OpenShift:**

```bash
oc kustomize deploy/overlays/qa/ | oc apply -f -
```

## Stack

- **Red Hat OpenShift** (RHDP sandbox on AWS)
- **Python/Flask** (single pod — event ingestion, SSE, telemetry, all routes)
- **Vanilla HTML/CSS/JS** (no frameworks)
- **Server-Sent Events** (real-time push to dashboard + presentations)
- **CloudEvents v1.0** (structured event payloads)
- **Persistent state** (JSON flush to PVC every 10s, SIGTERM handler)
- **Red Hat fonts** (Red Hat Display, Red Hat Text, Red Hat Mono)

## Repository layout

```
.
├── north/                 # Flask service (the only pod)
│   ├── app.py             # Event ingestion, SSE, telemetry, all routes
│   ├── stage/             # Dashboard, presentations, evidence panel, QR page
│   │   ├── dashboard.html
│   │   ├── present.html, present-rh.html, present-dtw.html, ...
│   │   ├── present-index.html
│   │   ├── about.html     # Evidence panel
│   │   └── qr.html
│   ├── assets/            # Static assets (mounted via ConfigMap)
│   └── Containerfile      # UBI9/python-311 container build
├── south-ui/              # Mobile wumpus game HTML
│   └── index.html         # Served by north at /play (via ConfigMap)
├── deploy/                # GitOps-ready kustomize manifests
│   ├── base/              # Cluster-agnostic resources
│   └── overlays/qa/       # QA environment patches
├── docs/                  # GitHub Pages (architecture diagram, Chloe assets)
│   ├── architecture.html
│   └── assets/chloe/      # Chloe character images (WebP)
├── transport/             # Artifact sync scripts
└── .github/               # CI, templates, community docs
```

## Built with

- **Claude Code** (Opus) — deployment, git ops, cluster management, pipeline debugging
- **Claude Web** (Opus) — UI design, game logic, presentation, architecture diagrams
- **ChatGPT** — Chloe character design, slide imagery

## Contributing

See [CONTRIBUTING.md](.github/CONTRIBUTING.md) for guidelines.

## License

[Apache-2.0](LICENSE)
