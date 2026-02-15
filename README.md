# OHC Edge Demo — Red Hat x SAP

Live interactive demo: physical security events flowing from edge devices through Red Hat OpenShift and SAP Edge Integration Cell to SAP BTP.

## Architecture

```
Phone (edge device) --> POST /ingest --> Flask on OpenShift --> SSE --> Stage dashboard
```

Each game action generates realistic Lenel OnGuard access control events in CloudEvents format.

[View the animated architecture diagram](https://jodonnel.github.io/ohc-sap-demo/architecture.html)

## Live URLs

| Endpoint | Description |
|----------|-------------|
| `/present` | Keyboard-driven presentation (10 slides, live dashboard, SSE) |
| `/stage` | Stage dashboard (event counter, telemetry) |
| `/play` | Mobile wumpus game (Lenel OnGuard badge events) |
| `/qr` | QR code page for projector |
| `/ingest` | POST endpoint for CloudEvents |
| `/events` | Server-Sent Events stream |
| `/state` | Current state JSON |
| `/telemetry` | Aggregated device telemetry |
| `/log` | Event history (last 200) |

## Running locally

Open `north/stage/present.html` in a browser — the built-in simulator runs without a server.

For the full stack:

```bash
cd north/
pip install flask
python app.py
# Presentation:  http://localhost:8080/present
# Dashboard:     http://localhost:8080/stage
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
- **Python/Flask** (north pod — event ingestion, SSE, telemetry)
- **Vanilla HTML/CSS/JS** (no frameworks)
- **Server-Sent Events** (real-time push)
- **CloudEvents format** (structured event payloads)
- **Red Hat fonts** (Red Hat Display, Red Hat Text, Red Hat Mono)

## Repository layout

```
.
├── north/                 # IT-side Flask service + presentation
│   ├── app.py             # Event ingestion, SSE, telemetry, routes
│   ├── stage/             # dashboard.html, present.html, qr.html
│   └── Containerfile      # UBI9/python-311 container build
├── south-ui/              # Edge-facing mobile wumpus game
│   └── index.html         # Served via ConfigMap + httpd
├── deploy/                # GitOps-ready kustomize manifests
│   ├── base/              # Cluster-agnostic resources
│   └── overlays/qa/       # QA environment patches
├── docs/                  # Architecture diagram (GitHub Pages)
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
