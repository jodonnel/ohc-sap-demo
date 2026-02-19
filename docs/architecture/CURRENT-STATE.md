# Current Architecture — OHC Demo System
**Date:** 2026-02-19
**Status:** PRODUCTION (qr-demo-qa namespace)
**Commit:** ecf3b15
**Route:** https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com

---

## What's Deployed Right Now

### Working Demos
- `/stage` — Real-time event dashboard (SSE stream)
- `/play` — Mobile badge tap game
- `/labs` — Feature voting page (11 use cases)
- `/present-index` — Presentation launcher
- **Presentation decks (15 total):**
  - `/present` — General SAP customers
  - `/present-util` — Utilities vertical
  - `/present-rail` — Rail vertical
  - `/present-ad` — Aerospace & Defense
  - `/present-rh` — Red Hat sellers
  - `/present-dtw` — Demo to Win (Beta)
  - `/present-piport` — PI/PO EOL Migration (#41)
  - `/present-grc` — 3D-GRC Kill Chain (#42)
  - `/present-shopfloor` — Visual Inspection (#43)
  - `/present-openblue` — OpenBlue (#45)
  - `/present-mii` — MII/ME Coexistence (#47)
  - `/present-substation` — Energy Anomaly (#48)
  - `/present-blackjack` — Meta Glasses Blackjack (#50)
  - `/present-job-coach` — Job Coach for IDD adults (Brian)

### Architecture (Current — "Amateur Hour")

```
┌─────────────────────────────────────────────────┐
│  Flask App (north)                              │
│  - Serves HTML from ConfigMaps                  │
│  - SSE events stream                            │
│  - POST endpoints for scenarios                 │
│  - State in Python dicts (in-memory)            │
└─────────────────────────────────────────────────┘
          ↓ mounts
┌─────────────────────────────────────────────────┐
│  ConfigMaps (3 total)                           │
│  - north-app: app.py (Flask code)               │
│  - north-stage-dashboard: 15+ HTML files        │
│  - north-assets: Mario coin sound (base64)      │
└─────────────────────────────────────────────────┘
          ↓ mounts
┌─────────────────────────────────────────────────┐
│  PersistentVolumeClaim                          │
│  - /data (state.json, event logs)               │
└─────────────────────────────────────────────────┘
```

### What's Wrong With This

1. **ConfigMaps for content** — ConfigMaps are for configuration, not static assets. We're stuffing HTML files into ConfigMaps and patching them on every content change.

2. **No separation of concerns** — Flask serves both API endpoints AND static files. Should be nginx for static, Flask for dynamic.

3. **No CI/CD** — Manual `oc patch configmap` + `oc delete pod` workflow. No build pipeline.

4. **In-memory state** — `count`, `last`, `event_log` all in Python dicts. Lost on pod restart. Can't scale horizontally.

5. **3MB ConfigMap limit** — Can't embed videos. Tried to embed 6.2MB of base64 video in HTML, hit hard limit. Current workaround: emoji placeholders.

6. **No caching** — Every request hits Flask. No CDN, no browser caching headers.

7. **Monolithic HTML files** — No components, lots of duplication. Every presentation deck copy-pastes the same CSS/JS.

### What Works Well

- **SSE for real-time events** — Simple, effective, no WebSocket complexity
- **CloudEvents schema** — Clean event model
- **Self-contained deployment** — No external dependencies
- **Narrative-driven presentations** — Story structure is strong
- **OpenShift-native** — Runs on target platform

---

## Current File Structure

```
north/
├── app.py                    # Flask app (395 lines)
├── Containerfile             # UBI9 + python311
├── stage/
│   ├── dashboard.html        # SSE dashboard
│   ├── present-*.html        # 15 presentation decks
│   ├── labs.html             # Feature voting page
│   ├── play.html             # Mobile game
│   └── assets/
│       └── videos/           # NOT DEPLOYED (too large for ConfigMap)
│           ├── disclaimer.mp4
│           └── winning.mp4
└── requirements.txt          # flask only
```

---

## Deployment Workflow (Current)

**When content changes:**
```bash
# 1. Edit HTML file locally
vim north/stage/present-foo.html

# 2. Commit to git
git add north/stage/present-foo.html
git commit -m "update: foo presentation"
git push

# 3. Patch ConfigMap (MANUAL)
python3 <<EOF
import json, subprocess
with open("north/stage/present-foo.html") as f:
    patch = {"data": {"present-foo.html": f.read()}}
subprocess.run(["oc", "patch", "configmap", "north-stage-dashboard",
                "--type", "merge", "-p", json.dumps(patch)])
EOF

# 4. Restart pod to pick up new ConfigMap
oc delete pod -l app=north

# 5. Wait for new pod to start (~10 sec)
# 6. Verify route returns 200
```

**This is not how real applications work.**

---

## State Management (Current)

All state lives in Python global variables:

```python
count = 0                    # Total events fired
last = {}                    # Last event by class
last_event_time = None       # Timestamp
event_log = []               # Last 100 events (deque)
telemetry = defaultdict(int) # Event counts by type
_contractor_swipes = {}      # Contractor time tracking
```

**Problems:**
- Lost on pod restart
- Can't run multiple replicas (state diverges)
- No persistence
- No audit trail

**Current workaround:**
`/flush` endpoint writes `state.json` to `/data` PVC, but it's manual and unreliable.

---

## Routes (Current)

| Route | Handler | Source |
|---|---|---|
| `/` | redirect → `/present-index` | app.py |
| `/stage` | HTML | ConfigMap |
| `/play` | HTML | ConfigMap |
| `/labs` | HTML | ConfigMap |
| `/present-index` | HTML | ConfigMap |
| `/present-*` (15 decks) | HTML | ConfigMap |
| `/assets/<file>` | static | ConfigMap (binary) |
| `/events` | SSE stream | app.py (runtime) |
| `/badge/tap` | POST | app.py |
| `/scenario/*` | POST | app.py |
| `/piport/idoc` | POST | app.py |
| `/shopfloor/*` | POST | app.py |
| `/contractor/*` | POST | app.py |
| `/openblue/*` | POST | app.py |
| `/ot/*` | POST | app.py |
| `/ingest/*` | POST | app.py |

---

## Known Issues

1. **Videos can't deploy** — Blackjack presentation has 4.7MB of video. ConfigMap limit is 3MB. Current version uses emoji placeholders.

2. **No rollback mechanism** — If a ConfigMap patch breaks something, manual rollback from git.

3. **No staging environment** — Changes go straight to production.

4. **No monitoring** — No metrics, no logging aggregation, no alerts.

5. **Single replica** — Can't scale horizontally due to in-memory state.

6. **No HTTPS redirect** — Route accepts HTTP (cluster handles TLS termination, but no force-HTTPS).

---

## Backup Snapshot

**Taken:** 2026-02-19 05:30 UTC
**Location:** `backups/`
**Files:**
- `stage-configmap-20260219-053000.yaml` — All HTML files
- `app-configmap-20260219-053000.yaml` — Flask app
- `assets-configmap-20260219-053000.yaml` — Binary assets
- `north-deployment-20260219-053000.yaml` — Deployment spec

**Git tag:** `snapshot-before-rebuild-20260219`

**To restore:**
```bash
oc apply -f backups/stage-configmap-20260219-053000.yaml
oc apply -f backups/app-configmap-20260219-053000.yaml
oc apply -f backups/north-deployment-20260219-053000.yaml
oc delete pod -l app=north
```

---

## What's Next

See `REBUILD-PLAN.md` for proposed architecture changes.

**Current site remains live** during rebuild. New architecture will be built in `qr-demo-dev` namespace, tested thoroughly, then promoted to production.

**No downtime. Full rollback capability.**
