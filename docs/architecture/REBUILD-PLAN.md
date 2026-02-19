# Architecture Rebuild Plan — OHC Demo System
**Date:** 2026-02-19
**Author:** CC (Claude Code) + Jim O'Donnell
**Status:** PROPOSED (awaiting approval)
**Risk:** LOW (parallel build, zero downtime)

---

## Why Rebuild

Current architecture stuffs static assets into ConfigMaps, uses Flask to serve HTML files, and stores state in Python dicts. This is "amateur hour" — not how professional web applications are built.

**Problems with current approach:**
1. ConfigMaps for content (they're for config, not assets)
2. 3MB ConfigMap limit prevents video deployment
3. No separation between static content and dynamic API
4. Manual deployment workflow (`oc patch` + `oc delete pod`)
5. In-memory state (lost on restart, can't scale horizontally)
6. No CI/CD pipeline

**Why it matters:**
- Can't deploy the blackjack video presentation (file too large)
- Can't add more rich media demos (images, videos, animations)
- Can't scale to multiple replicas
- Brittle deployment process (one bad patch breaks everything)
- No staging environment (changes go straight to production)

---

## Proposed Architecture

```
┌─────────────────────────────────────────────────┐
│  nginx (static content server)                  │
│  - Serves /stage/, /play, /labs from PVC        │
│  - Serves /videos/, /images/ from PVC           │
│  - Browser caching headers                      │
│  - Gzip compression                             │
└─────────────────────────────────────────────────┘
          ↓ proxy_pass /api/*
┌─────────────────────────────────────────────────┐
│  Flask API (dynamic endpoints only)             │
│  - /events (SSE stream)                         │
│  - /badge/tap, /scenario/*, /ingest/* (POST)    │
│  - Event emission, scenario playback            │
└─────────────────────────────────────────────────┘
          ↓
┌─────────────────────────────────────────────────┐
│  Redis (state + pub/sub)                        │
│  - Event counts, last events, telemetry         │
│  - SSE pub/sub (multi-replica safe)             │
│  - Persistent (survives pod restart)            │
└─────────────────────────────────────────────────┘
          ↓
┌─────────────────────────────────────────────────┐
│  PersistentVolume (static assets)               │
│  - /stage/*.html (presentation decks)           │
│  - /videos/*.mp4 (blackjack, future demos)      │
│  - /images/*.{png,jpg} (storyboards, diagrams)  │
└─────────────────────────────────────────────────┘
```

### Component Breakdown

**1. nginx (new)**
- Serves all static files (HTML, CSS, JS, images, videos)
- Mounted from PVC at `/usr/share/nginx/html`
- ConfigMap only holds `nginx.conf` (actual config, not content)
- Proxies `/api/*` to Flask backend
- Sets caching headers, compression

**2. Flask API (refactored)**
- Only handles dynamic endpoints
- No `send_from_directory` calls
- Connects to Redis for state
- Publishes SSE events via Redis pub/sub (multi-replica safe)

**3. Redis (new)**
- Stores event counts, last events, telemetry
- Pub/sub for SSE (allows horizontal scaling)
- Persistent volume (data survives restart)

**4. PVC (expanded use)**
- Already exists, currently used for `/data/state.json`
- Will hold all static assets
- Mounted to nginx container, not Flask

---

## Deployment Strategy (Zero Downtime)

### Phase 1: Build in Parallel Namespace

**Create new namespace:**
```bash
oc new-project qr-demo-dev
```

**Deploy new architecture:**
1. Create Redis deployment
2. Create nginx deployment (with PVC mount)
3. Deploy refactored Flask app (connects to Redis)
4. Copy static assets to PVC
5. Test at `https://north-qr-demo-dev.apps.cluster...`

**Current production (`qr-demo-qa`) remains untouched.**

### Phase 2: Validation

Test all functionality in dev:
- [ ] Dashboard loads and shows events
- [ ] SSE stream works
- [ ] Badge tap fires events
- [ ] All 15 presentation decks load
- [ ] Videos play (blackjack disclaimer + winning)
- [ ] Labs page voting works
- [ ] Multi-replica test (scale to 3 pods, verify state sync)

### Phase 3: Cutover

**Option A: Route update (instant cutover)**
```bash
# Update production route to point to new deployment
oc patch route north -n qr-demo-qa -p '{"spec":{"to":{"name":"north-v2"}}}'
```

**Option B: Blue/green (gradual cutover)**
```bash
# Run both versions, split traffic 90/10, then 50/50, then 0/100
oc set route-backends north north-v1=10 north-v2=90
```

**Option C: New route (safest)**
```bash
# Keep old route, create new route, test thoroughly, then delete old
oc create route edge north-v2 --service=north-v2
# Test at https://north-v2-qr-demo-qa.apps...
# When confident, delete old route and rename new route
```

### Phase 4: Cleanup

After 48 hours of stable operation:
- Delete old ConfigMaps (north-stage-dashboard)
- Remove old deployment
- Tag git: `production-rebuild-complete-20260219`

---

## Rollback Plan

**If new architecture fails:**

1. **Instant rollback** — Update route to point back to old deployment:
   ```bash
   oc patch route north -p '{"spec":{"to":{"name":"north-v1"}}}'
   ```

2. **Full rollback** — Restore from backup:
   ```bash
   cd backups/
   oc apply -f stage-configmap-20260219-053000.yaml
   oc apply -f app-configmap-20260219-053000.yaml
   oc apply -f north-deployment-20260219-053000.yaml
   oc delete pod -l app=north
   ```

3. **Git rollback** — Revert to snapshot commit:
   ```bash
   git revert ecf3b15..HEAD
   git push
   ```

**Expected rollback time:** < 5 minutes
**Data loss:** None (events are ephemeral, state already not persisted in current version)

---

## File Structure (After Rebuild)

```
north/
├── api/
│   ├── app.py              # Flask API only (no static serving)
│   ├── events.py           # SSE stream + Redis pub/sub
│   ├── scenarios.py        # Scenario playback logic
│   └── requirements.txt    # flask, redis, gunicorn
├── static/                 # Built artifacts (copied to PVC)
│   ├── stage/
│   │   ├── dashboard.html
│   │   ├── present-*.html
│   │   ├── labs.html
│   │   └── play.html
│   ├── videos/
│   │   ├── disclaimer.mp4
│   │   └── winning.mp4
│   └── images/
│       └── storyboards/
├── nginx/
│   ├── nginx.conf          # nginx config
│   └── Containerfile       # nginx + static files
├── deploy/
│   ├── redis.yaml
│   ├── nginx-deployment.yaml
│   ├── api-deployment.yaml
│   ├── pvc.yaml
│   └── route.yaml
└── docs/
    └── architecture/
        ├── CURRENT-STATE.md    # This file
        └── REBUILD-PLAN.md     # You are here
```

---

## Deployment Workflow (After Rebuild)

**When content changes:**

```bash
# 1. Edit HTML file
vim north/static/stage/present-foo.html

# 2. Commit to git
git add north/static/stage/present-foo.html
git commit -m "update: foo presentation"
git push

# 3. CI/CD pipeline (GitHub Actions or Tekton)
# - Builds nginx container with new static files
# - Pushes to registry
# - Updates deployment
# - Rolls out new pods (zero downtime)

# OR manual (if no CI/CD):
oc cp north/static/stage/present-foo.html deployment/nginx:/usr/share/nginx/html/stage/
# nginx picks up new file instantly (no pod restart needed)
```

**When API changes:**

```bash
# 1. Edit app.py
vim north/api/app.py

# 2. Commit to git
git add north/api/app.py
git commit -m "feat: new scenario endpoint"
git push

# 3. Build new container
podman build -t quay.io/jodonnell/north-api:latest north/api/
podman push quay.io/jodonnell/north-api:latest

# 4. Rolling update (zero downtime)
oc set image deployment/north-api api=quay.io/jodonnell/north-api:latest
oc rollout status deployment/north-api
```

---

## Timeline

**Total estimated time:** 3-4 hours
**Downtime:** 0 minutes

| Phase | Duration | Parallelizable? |
|---|---|---|
| Redis deployment | 15 min | No |
| nginx + PVC setup | 30 min | After Redis |
| Flask refactor (remove static serving) | 45 min | Parallel with nginx |
| Flask Redis integration | 30 min | After Flask refactor |
| Copy static assets to PVC | 15 min | After nginx |
| Test in dev namespace | 60 min | After all above |
| Cutover to prod | 15 min | After testing |
| Monitoring/validation | 30 min | After cutover |

**Can start immediately** or wait until after SAP Insider (26 days out).

---

## Open Questions

1. **Redis deployment** — Use built-in OpenShift Redis template, or custom deployment?
2. **Container registry** — Quay.io (public) or internal OpenShift registry?
3. **CI/CD** — GitHub Actions, Tekton, or manual for now?
4. **Monitoring** — Prometheus + Grafana, or just pod logs for now?
5. **Video hosting** — Keep on PVC, or move to S3/CloudFront later?

---

## Approval Needed

- [ ] Jim approves architecture changes
- [ ] Confirm: build in `qr-demo-dev`, test thoroughly, then cutover
- [ ] Confirm: current site stays live during rebuild
- [ ] Confirm: rollback plan understood and accepted
- [ ] Go/no-go decision: rebuild now or after SAP Insider?

**Signed off by:** _______________
**Date:** _______________
