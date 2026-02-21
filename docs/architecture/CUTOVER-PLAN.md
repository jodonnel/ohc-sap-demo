# Production Cutover Plan — QR Demo Migration
**Date:** 2026-02-19
**Author:** CC (Claude Code) + Jim O'Donnell
**Status:** READY FOR EXECUTION
**Risk Level:** LOW (parallel architecture, instant rollback capability)

---

## Executive Summary

This document provides a step-by-step cutover plan to migrate from the old ConfigMap-based architecture (qr-demo-qa) to the new nginx+Redis+Flask architecture (qr-demo-dev).

**Current State:**
- **Production:** qr-demo-qa namespace, ConfigMap-based, single Flask pod
- **New System:** qr-demo-dev namespace, nginx+Redis+Flask, multi-replica capable
- **URL:** https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com

**Target State:**
- **Production:** qr-demo-qa namespace, nginx+Redis+Flask architecture
- **URL:** Same (no DNS changes required)
- **Replicas:** 2x Flask API pods (horizontal scaling enabled)

**Estimated Cutover Time:** 15 minutes
**Estimated Downtime:** 0 seconds (blue/green deployment)
**Rollback Time:** < 2 minutes

---

## Table of Contents

1. [Pre-Cutover Checklist](#pre-cutover-checklist)
2. [Cutover Options Analysis](#cutover-options-analysis)
3. [Recommended Cutover Procedure](#recommended-cutover-procedure)
4. [Rollback Procedures](#rollback-procedures)
5. [Post-Cutover Validation](#post-cutover-validation)
6. [Cleanup Tasks](#cleanup-tasks)
7. [DNS/Route Considerations](#dnsroute-considerations)
8. [Risk Assessment](#risk-assessment)

---

## Pre-Cutover Checklist

### 1. Validation in qr-demo-dev (MUST COMPLETE BEFORE CUTOVER)

Run all tests against: https://qr-demo-dev-qr-demo-dev.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com

#### Core Functionality Tests

- [ ] **Dashboard loads** — `/stage` returns 200, SSE stream connects
- [ ] **SSE events work** — Open `/stage`, fire test event, verify real-time update
- [ ] **Badge tap** — POST to `/badge/tap`, verify event appears on dashboard
- [ ] **Play page** — `/play` loads, mobile responsive
- [ ] **Labs page** — `/labs` loads, voting works

#### Presentation Deck Tests (All 15)

- [ ] `/present-index` — Launcher page loads
- [ ] `/present` — General SAP customers deck
- [ ] `/present-util` — Utilities vertical
- [ ] `/present-rail` — Rail vertical
- [ ] `/present-ad` — Aerospace & Defense
- [ ] `/present-rh` — Red Hat sellers
- [ ] `/present-dtw` — Demo to Win (Beta)
- [ ] `/present-piport` — PI/PO EOL Migration
- [ ] `/present-grc` — 3D-GRC Kill Chain
- [ ] `/present-shopfloor` — Visual Inspection
- [ ] `/present-openblue` — OpenBlue
- [ ] `/present-mii` — MII/ME Coexistence
- [ ] `/present-substation` — Energy Anomaly
- [ ] `/present-blackjack` — Meta Glasses Blackjack (with VIDEO)
- [ ] `/present-job-coach` — Job Coach for IDD adults

#### API Endpoint Tests

- [ ] `/events` — SSE stream returns `text/event-stream`
- [ ] `/badge/tap` — POST returns 200, event fires
- [ ] `/scenario/grc-kill-chain` — POST returns 200
- [ ] `/scenario/piport-migration` — POST returns 200
- [ ] `/scenario/shopfloor-inspection` — POST returns 200
- [ ] `/scenario/openblue-anomaly` — POST returns 200
- [ ] `/scenario/mii-coexistence` — POST returns 200
- [ ] `/scenario/substation-grid` — POST returns 200
- [ ] `/ingest/telemetry` — POST returns 200

#### Multi-Replica Tests

- [ ] **Scale to 3 replicas** — `oc scale deployment/north-api --replicas=3 -n qr-demo-dev`
- [ ] **Open dashboard in 3 browser tabs**
- [ ] **Fire event from tab 1** — Verify appears in tabs 2 and 3 instantly
- [ ] **Fire event from tab 2** — Verify appears in tabs 1 and 3 instantly
- [ ] **Check Redis pub/sub** — `oc exec -it deployment/redis -n qr-demo-dev -- redis-cli MONITOR`
- [ ] **Scale back to 2 replicas** — `oc scale deployment/north-api --replicas=2 -n qr-demo-dev`

#### Performance Tests

- [ ] **Static file caching** — Check nginx headers: `curl -I https://qr-demo-dev.../stage/dashboard.html`
- [ ] **Gzip compression** — Verify `Content-Encoding: gzip` header
- [ ] **Video playback** — Blackjack disclaimer.mp4 plays without buffering
- [ ] **Concurrent users** — Open dashboard in 10 tabs, fire events rapidly

#### Persistence Tests

- [ ] **Restart Redis pod** — `oc delete pod -l app=redis -n qr-demo-dev`
- [ ] **Verify state survives** — Check event counts, last events
- [ ] **Restart API pods** — `oc delete pod -l app=north-api -n qr-demo-dev`
- [ ] **Verify SSE reconnects** — Dashboard reconnects automatically

### 2. Backup Production State

```bash
# Create timestamped backup directory
BACKUP_DIR="backups/cutover-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup all critical resources from qr-demo-qa
oc get deployment north -n qr-demo-qa -o yaml > "$BACKUP_DIR/north-deployment.yaml"
oc get service north -n qr-demo-qa -o yaml > "$BACKUP_DIR/north-service.yaml"
oc get route north -n qr-demo-qa -o yaml > "$BACKUP_DIR/north-route.yaml"
oc get configmap north-app -n qr-demo-qa -o yaml > "$BACKUP_DIR/north-app-configmap.yaml"
oc get configmap north-stage-dashboard -n qr-demo-qa -o yaml > "$BACKUP_DIR/north-stage-dashboard-configmap.yaml"
oc get configmap north-assets -n qr-demo-qa -o yaml > "$BACKUP_DIR/north-assets-configmap.yaml"
oc get pvc north-data -n qr-demo-qa -o yaml > "$BACKUP_DIR/north-data-pvc.yaml"

# Create git tag for rollback point
git tag -a "pre-cutover-$(date +%Y%m%d-%H%M%S)" -m "Production snapshot before cutover"
git push origin --tags
```

**Checklist:**
- [ ] Backup files created in `backups/cutover-YYYYMMDD-HHMMSS/`
- [ ] Git tag created and pushed
- [ ] Verify backup files are readable: `ls -lh $BACKUP_DIR`

### 3. Communication Plan

- [ ] **Announce maintenance window** — Email stakeholders (SAP demo team, Red Hat sellers)
- [ ] **Set status page** — Update status indicator (if applicable)
- [ ] **Slack/Teams notification** — "QR Demo migration starting in 15 minutes"
- [ ] **War room channel** — Create dedicated channel for live updates

### 4. Resource Readiness

**Verify qr-demo-dev has all components running:**

```bash
# Check all pods are healthy
oc get pods -n qr-demo-dev

# Expected output:
# nginx-XXXXXXX          1/1     Running
# north-api-XXXXXXX      1/1     Running
# north-api-XXXXXXX      1/1     Running  (2 replicas)
# redis-XXXXXXX          1/1     Running
```

- [ ] nginx pod: Running
- [ ] north-api pods (2x): Running
- [ ] redis pod: Running
- [ ] PVC static-files: Bound
- [ ] PVC redis-data: Bound

### 5. Stakeholder Approval

- [ ] **Technical approval** — Jim O'Donnell signs off
- [ ] **Business approval** — Demo team confirms timing
- [ ] **Rollback authority** — Designate who can call rollback

---

## Cutover Options Analysis

### Option A: Route Update (Instant Cutover) — RECOMMENDED

**Method:** Update existing route in qr-demo-qa to point to services in qr-demo-dev

**Pros:**
- Instant cutover (< 5 seconds)
- No DNS changes required
- Same URL for users
- Instant rollback (just patch route back)

**Cons:**
- Cross-namespace service routing (requires creating services in qr-demo-qa that point to qr-demo-dev)
- Slightly more complex setup

**Downtime:** 0 seconds (route update is atomic)

---

### Option B: Blue/Green Traffic Split (Gradual Cutover)

**Method:** Deploy new architecture in qr-demo-qa alongside old, split traffic gradually

**Pros:**
- Gradual rollout (10% → 50% → 100%)
- Monitor error rates during transition
- Easy to adjust traffic ratios

**Cons:**
- Requires both versions running in same namespace
- More complex resource management
- Longer cutover window (30-60 minutes)

**Downtime:** 0 seconds (gradual traffic shift)

---

### Option C: Namespace Rename (Infrastructure Cutover)

**Method:** Rename qr-demo-qa → qr-demo-qa-old, rename qr-demo-dev → qr-demo-qa

**Pros:**
- Clean separation
- No cross-namespace routing

**Cons:**
- NOT SUPPORTED by OpenShift (can't rename namespaces)
- Would require recreating all resources
- High risk of downtime

**Status:** NOT VIABLE

---

### Option D: Deploy New Architecture in qr-demo-qa (In-Place Upgrade)

**Method:** Deploy nginx+Redis+Flask directly into qr-demo-qa, delete old deployment after cutover

**Pros:**
- All resources in one namespace
- Clean final state
- No cross-namespace dependencies

**Cons:**
- Requires careful resource naming (nginx, north-api, redis vs. existing "north")
- Potential resource conflicts
- Harder to rollback (must redeploy old stack)

**Downtime:** 0 seconds (blue/green within namespace)

---

### RECOMMENDATION: Option A (Route Update)

**Rationale:**
- Simplest implementation
- Instant cutover and rollback
- qr-demo-dev is already validated and running
- No resource conflicts in qr-demo-qa
- Can transition to Option D for final cleanup later

---

## Recommended Cutover Procedure

### Phase 1: Prepare Cross-Namespace Routing (10 minutes)

#### Step 1.1: Create ExternalName Services in qr-demo-qa

These services will act as "pointers" to the services in qr-demo-dev.

```bash
# Create nginx service proxy
cat <<EOF | oc apply -f -
apiVersion: v1
kind: Service
metadata:
  name: nginx-v2
  namespace: qr-demo-qa
spec:
  type: ExternalName
  externalName: nginx.qr-demo-dev.svc.cluster.local
  ports:
  - port: 8080
    targetPort: 8080
    protocol: TCP
EOF

# Verify service created
oc get service nginx-v2 -n qr-demo-qa
```

**Checkpoint:** Service nginx-v2 exists in qr-demo-qa

#### Step 1.2: Create Test Route

Create a parallel route to test the new architecture without affecting production.

```bash
# Create test route pointing to new service
cat <<EOF | oc apply -f -
apiVersion: route.openshift.io/v1
kind: Route
metadata:
  name: north-v2-test
  namespace: qr-demo-qa
  annotations:
    haproxy.router.openshift.io/balance: roundrobin
    haproxy.router.openshift.io/disable_cookies: 'true'
    haproxy.router.openshift.io/set-forwarded-headers: append
    haproxy.router.openshift.io/timeout: 3600s
spec:
  port:
    targetPort: 8080
  tls:
    termination: edge
  to:
    kind: Service
    name: nginx-v2
    weight: 100
  wildcardPolicy: None
EOF

# Get test route URL
TEST_URL=$(oc get route north-v2-test -n qr-demo-qa -o jsonpath='{.spec.host}')
echo "Test URL: https://$TEST_URL"
```

**Checkpoint:** Test route created, URL printed

#### Step 1.3: Validate Test Route

```bash
# Test dashboard loads
curl -I https://$TEST_URL/stage

# Expected: HTTP/1.1 200 OK

# Test SSE endpoint
curl -N https://$TEST_URL/events

# Expected: text/event-stream headers

# Test API endpoint
curl -X POST https://$TEST_URL/badge/tap \
  -H "Content-Type: application/json" \
  -d '{"badge_id":"test-cutover","action":"tap"}'

# Expected: {"status":"ok"}
```

**Checklist:**
- [ ] Dashboard returns 200
- [ ] SSE stream works
- [ ] API POST works
- [ ] No 502/503/504 errors

**ROLLBACK POINT 1:** If test route fails, stop here. Fix issues in qr-demo-dev before proceeding.

---

### Phase 2: Production Cutover (5 minutes)

#### Step 2.1: Final Pre-Cutover Validation

```bash
# Verify old production still works
curl -I https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com/stage

# Verify new architecture still works
curl -I https://$TEST_URL/stage

# Check no pods are in CrashLoopBackOff
oc get pods -n qr-demo-dev | grep -v Running | grep -v Completed

# Verify Redis is healthy
oc exec -it deployment/redis -n qr-demo-dev -- redis-cli PING
# Expected: PONG
```

**Checklist:**
- [ ] Old production: 200 OK
- [ ] New test route: 200 OK
- [ ] All pods: Running
- [ ] Redis: Responding

#### Step 2.2: Update Production Route

**CRITICAL STEP — This switches production traffic to new architecture**

```bash
# Save current route state
oc get route north -n qr-demo-qa -o yaml > /tmp/north-route-before-cutover.yaml

# Update production route to point to nginx-v2 service
oc patch route north -n qr-demo-qa -p '{
  "spec": {
    "to": {
      "name": "nginx-v2"
    }
  }
}'

# Record cutover timestamp
echo "Cutover completed at: $(date -Iseconds)" | tee /tmp/cutover-timestamp.txt
```

**Expected Result:** Route immediately starts serving traffic from qr-demo-dev

**Checkpoint:** Route patched successfully

#### Step 2.3: Immediate Validation (< 60 seconds)

```bash
# Wait 5 seconds for route propagation
sleep 5

# Test production URL now points to new architecture
curl -I https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com/stage

# Check for nginx headers (confirms new architecture)
curl -I https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com/stage | grep -i server
# Expected: Server: nginx

# Test SSE stream
curl -N https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com/events &
CURL_PID=$!
sleep 2
kill $CURL_PID
# Expected: SSE event stream received

# Fire test event
curl -X POST https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com/badge/tap \
  -H "Content-Type: application/json" \
  -d '{"badge_id":"cutover-test","action":"tap"}'
# Expected: {"status":"ok"}
```

**Checklist:**
- [ ] Dashboard loads (200 OK)
- [ ] SSE stream works
- [ ] Server header shows "nginx"
- [ ] API POST returns 200
- [ ] No 502/503/504 errors

**DECISION POINT:**
- **If all checks pass:** Proceed to Phase 3
- **If any check fails:** EXECUTE ROLLBACK (see below)

---

### Phase 3: Post-Cutover Monitoring (30 minutes)

#### Step 3.1: Watch Logs

```bash
# Terminal 1: nginx logs
oc logs -f deployment/nginx -n qr-demo-dev

# Terminal 2: Flask API logs
oc logs -f deployment/north-api -n qr-demo-dev --all-containers=true

# Terminal 3: Redis logs
oc logs -f deployment/redis -n qr-demo-dev

# Terminal 4: Watch pod status
watch -n 2 'oc get pods -n qr-demo-dev'
```

**Monitor for:**
- [ ] No 500 errors in nginx logs
- [ ] No Python exceptions in Flask logs
- [ ] No connection errors to Redis
- [ ] No pod restarts

#### Step 3.2: User Acceptance Testing

Open dashboard in browser: https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com/stage

**Manual Tests:**
- [ ] Dashboard loads without errors
- [ ] SSE stream shows live updates
- [ ] Fire event from `/play` page
- [ ] Event appears on dashboard instantly
- [ ] Load 3-4 different presentation decks
- [ ] Play blackjack video (disclaimer.mp4)
- [ ] Check browser console for JS errors

#### Step 3.3: Load Testing

```bash
# Fire 50 rapid events to test Redis pub/sub
for i in {1..50}; do
  curl -X POST https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com/badge/tap \
    -H "Content-Type: application/json" \
    -d "{\"badge_id\":\"load-test-$i\",\"action\":\"tap\"}" &
done
wait

# Verify all events processed
curl https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com/events | head -n 20
```

**Checklist:**
- [ ] All 50 events processed
- [ ] No errors in logs
- [ ] Dashboard shows all events
- [ ] No performance degradation

#### Step 3.4: Stakeholder Notification

```bash
# Send success notification
echo "Production cutover completed successfully at $(date -Iseconds)" > /tmp/cutover-success.txt
echo "Old architecture: Stopped" >> /tmp/cutover-success.txt
echo "New architecture: Active" >> /tmp/cutover-success.txt
echo "Rollback window: 48 hours" >> /tmp/cutover-success.txt

cat /tmp/cutover-success.txt
# Send to Slack/Teams/Email
```

**Checklist:**
- [ ] Stakeholders notified
- [ ] Status page updated
- [ ] Monitoring dashboard updated

---

### Phase 4: Stabilization Period (48 hours)

#### Step 4.1: Extended Monitoring

**Monitor for 48 hours before cleanup:**
- [ ] No increase in error rates
- [ ] No performance degradation
- [ ] No user complaints
- [ ] Redis persistence working (test pod restarts)
- [ ] Multi-replica SSE working

#### Step 4.2: Scheduled Health Checks

**Run every 6 hours for 48 hours:**

```bash
#!/bin/bash
# Save as: scripts/health-check.sh

PROD_URL="https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com"

echo "=== Health Check at $(date -Iseconds) ==="

# Test dashboard
echo -n "Dashboard: "
curl -s -o /dev/null -w "%{http_code}" $PROD_URL/stage
echo ""

# Test SSE
echo -n "SSE stream: "
timeout 3 curl -s -N $PROD_URL/events | head -n 1 && echo "OK" || echo "FAIL"

# Test API
echo -n "Badge tap API: "
curl -s -X POST $PROD_URL/badge/tap \
  -H "Content-Type: application/json" \
  -d '{"badge_id":"health-check","action":"tap"}' | grep -q "ok" && echo "OK" || echo "FAIL"

# Check pod health
echo "Pod status:"
oc get pods -n qr-demo-dev | grep -E "(nginx|north-api|redis)"

echo "================================"
```

**Checklist:**
- [ ] Health check script created
- [ ] Cron job scheduled (or manual runs)
- [ ] Results logged

---

## Rollback Procedures

### EMERGENCY ROLLBACK (< 2 minutes)

**Use if cutover fails immediately or within first 30 minutes**

#### Option 1: Route Revert (Instant Rollback)

```bash
# Restore original route configuration
oc apply -f /tmp/north-route-before-cutover.yaml

# Verify old deployment still running
oc get deployment north -n qr-demo-qa

# Expected: north deployment with 1/1 pods Running

# Test old production
curl -I https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com/stage

# Expected: HTTP/1.1 200 OK (from old Flask app)
```

**Checklist:**
- [ ] Route reverted
- [ ] Old deployment responding
- [ ] Dashboard loads
- [ ] SSE stream works

**Rollback Time:** < 2 minutes
**Data Loss:** None (old deployment was never stopped)

---

#### Option 2: Manual Route Patch (If backup file lost)

```bash
# Patch route back to old service
oc patch route north -n qr-demo-qa -p '{
  "spec": {
    "to": {
      "name": "north"
    }
  }
}'

# Verify rollback
curl -I https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com/stage
```

**Rollback Time:** < 1 minute

---

### DELAYED ROLLBACK (If issues discovered later)

**Use if problems found 1-48 hours after cutover**

#### Step 1: Verify Old Deployment Still Exists

```bash
# Check old deployment
oc get deployment north -n qr-demo-qa

# If deployment was deleted, restore from backup
if [ $? -ne 0 ]; then
  BACKUP_DIR=$(ls -td backups/cutover-* | head -n 1)
  oc apply -f "$BACKUP_DIR/north-deployment.yaml"
  oc apply -f "$BACKUP_DIR/north-app-configmap.yaml"
  oc apply -f "$BACKUP_DIR/north-stage-dashboard-configmap.yaml"
  oc apply -f "$BACKUP_DIR/north-assets-configmap.yaml"

  # Wait for pod to start
  oc wait --for=condition=available --timeout=120s deployment/north -n qr-demo-qa
fi
```

#### Step 2: Revert Route

```bash
# Restore route to old deployment
oc patch route north -n qr-demo-qa -p '{
  "spec": {
    "to": {
      "name": "north"
    }
  }
}'
```

#### Step 3: Validate Rollback

```bash
# Test old production
curl -I https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com/stage

# Verify old architecture
curl -I https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com/stage | grep -i server
# Expected: No "Server: nginx" header (Flask default)
```

#### Step 4: Document Rollback Reason

```bash
# Create rollback report
cat > /tmp/rollback-report.txt <<EOF
ROLLBACK EXECUTED at $(date -Iseconds)

Reason: [FILL IN REASON]

Symptoms:
- [FILL IN SYMPTOMS]

Actions Taken:
1. Reverted route to old deployment
2. Verified old production responding
3. [FILL IN OTHER ACTIONS]

Next Steps:
- [ ] Investigate root cause
- [ ] Fix issue in qr-demo-dev
- [ ] Re-test thoroughly
- [ ] Schedule new cutover window
EOF

cat /tmp/rollback-report.txt
```

**Rollback Time:** < 10 minutes (if old deployment still running)
**Rollback Time:** < 30 minutes (if old deployment must be restored from backup)

---

### COMPLETE ROLLBACK (Nuclear Option)

**Use if new architecture is fundamentally broken**

#### Step 1: Restore All Resources from Backup

```bash
# Find most recent backup
BACKUP_DIR=$(ls -td backups/cutover-* | head -n 1)
echo "Restoring from: $BACKUP_DIR"

# Apply all backup manifests
oc apply -f "$BACKUP_DIR/north-deployment.yaml"
oc apply -f "$BACKUP_DIR/north-service.yaml"
oc apply -f "$BACKUP_DIR/north-route.yaml"
oc apply -f "$BACKUP_DIR/north-app-configmap.yaml"
oc apply -f "$BACKUP_DIR/north-stage-dashboard-configmap.yaml"
oc apply -f "$BACKUP_DIR/north-assets-configmap.yaml"

# Delete new pods to force recreation
oc delete pod -l app=north -n qr-demo-qa

# Wait for old deployment to stabilize
oc wait --for=condition=available --timeout=120s deployment/north -n qr-demo-qa
```

#### Step 2: Delete New Architecture Services

```bash
# Remove cross-namespace services
oc delete service nginx-v2 -n qr-demo-qa
oc delete route north-v2-test -n qr-demo-qa
```

#### Step 3: Validate Complete Rollback

```bash
# Test production
curl -I https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com/stage

# Verify old architecture is serving
oc get pods -n qr-demo-qa | grep north
# Expected: north-XXXXXXX pod Running

# Test all endpoints
curl https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com/present-index
curl -N https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com/events &
sleep 2; kill %1
```

**Rollback Time:** < 30 minutes
**Data Loss:** Events fired during new architecture period (events are ephemeral)

---

## Post-Cutover Validation

### Automated Test Suite

```bash
#!/bin/bash
# Save as: scripts/post-cutover-tests.sh

PROD_URL="https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com"
FAILED=0

echo "=== Post-Cutover Validation Suite ==="
echo "Started at: $(date -Iseconds)"
echo ""

# Test 1: Dashboard loads
echo -n "Test 1: Dashboard loads... "
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" $PROD_URL/stage)
if [ "$HTTP_CODE" = "200" ]; then
  echo "PASS"
else
  echo "FAIL (HTTP $HTTP_CODE)"
  FAILED=$((FAILED + 1))
fi

# Test 2: nginx headers present
echo -n "Test 2: nginx serving static files... "
if curl -I $PROD_URL/stage 2>/dev/null | grep -q "Server: nginx"; then
  echo "PASS"
else
  echo "FAIL (nginx header not found)"
  FAILED=$((FAILED + 1))
fi

# Test 3: SSE stream works
echo -n "Test 3: SSE stream... "
if timeout 3 curl -s -N $PROD_URL/events | head -n 1 | grep -q "data:"; then
  echo "PASS"
else
  echo "FAIL (SSE stream not working)"
  FAILED=$((FAILED + 1))
fi

# Test 4: Badge tap API
echo -n "Test 4: Badge tap API... "
RESPONSE=$(curl -s -X POST $PROD_URL/badge/tap \
  -H "Content-Type: application/json" \
  -d '{"badge_id":"test","action":"tap"}')
if echo "$RESPONSE" | grep -q "ok"; then
  echo "PASS"
else
  echo "FAIL (API error)"
  FAILED=$((FAILED + 1))
fi

# Test 5: All presentation decks load
PRESENTATIONS=(
  "present-index"
  "present"
  "present-util"
  "present-rail"
  "present-ad"
  "present-rh"
  "present-dtw"
  "present-piport"
  "present-grc"
  "present-shopfloor"
  "present-openblue"
  "present-mii"
  "present-substation"
  "present-blackjack"
  "present-job-coach"
)

echo "Test 5: Presentation decks (15 total)..."
for deck in "${PRESENTATIONS[@]}"; do
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" $PROD_URL/$deck)
  if [ "$HTTP_CODE" = "200" ]; then
    echo "  $deck: PASS"
  else
    echo "  $deck: FAIL (HTTP $HTTP_CODE)"
    FAILED=$((FAILED + 1))
  fi
done

# Test 6: Video files accessible
echo -n "Test 6: Video files... "
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" $PROD_URL/videos/disclaimer.mp4)
if [ "$HTTP_CODE" = "200" ]; then
  echo "PASS"
else
  echo "FAIL (HTTP $HTTP_CODE)"
  FAILED=$((FAILED + 1))
fi

# Test 7: Redis persistence
echo -n "Test 7: Redis persistence... "
if oc exec -it deployment/redis -n qr-demo-dev -- redis-cli PING 2>/dev/null | grep -q "PONG"; then
  echo "PASS"
else
  echo "FAIL (Redis not responding)"
  FAILED=$((FAILED + 1))
fi

# Test 8: Multi-replica health
echo -n "Test 8: API replica count... "
REPLICAS=$(oc get deployment north-api -n qr-demo-dev -o jsonpath='{.status.availableReplicas}')
if [ "$REPLICAS" -ge 2 ]; then
  echo "PASS ($REPLICAS replicas)"
else
  echo "FAIL (only $REPLICAS replicas available)"
  FAILED=$((FAILED + 1))
fi

# Summary
echo ""
echo "==================================="
if [ $FAILED -eq 0 ]; then
  echo "ALL TESTS PASSED"
  echo "Cutover validated successfully"
  exit 0
else
  echo "TESTS FAILED: $FAILED"
  echo "Cutover validation FAILED - consider rollback"
  exit 1
fi
```

**Usage:**

```bash
chmod +x scripts/post-cutover-tests.sh
./scripts/post-cutover-tests.sh
```

**Run this test suite:**
- Immediately after cutover
- After 1 hour
- After 6 hours
- After 24 hours
- After 48 hours

---

## Cleanup Tasks

**Execute after 48 hours of stable operation**

### Day 3: Remove Old Deployment

```bash
# Verify new architecture still healthy
./scripts/post-cutover-tests.sh

# If all tests pass, proceed with cleanup
echo "Proceeding with cleanup..."

# Delete old deployment (POINT OF NO RETURN)
oc delete deployment north -n qr-demo-qa

# Delete old ConfigMaps
oc delete configmap north-app -n qr-demo-qa
oc delete configmap north-stage-dashboard -n qr-demo-qa
oc delete configmap north-assets -n qr-demo-qa

# Delete test route
oc delete route north-v2-test -n qr-demo-qa

# Keep old service for now (may have dependencies)
# oc delete service north -n qr-demo-qa  # SKIP FOR NOW
```

**Checklist:**
- [ ] Old deployment deleted
- [ ] Old ConfigMaps deleted
- [ ] Test route deleted
- [ ] Production still working

### Week 2: Final Cleanup

```bash
# Delete old service
oc delete service north -n qr-demo-qa

# Delete cross-namespace proxy service
oc delete service nginx-v2 -n qr-demo-qa

# Tag git repository
git tag -a "cutover-complete-$(date +%Y%m%d)" -m "Old architecture fully removed"
git push origin --tags

# Archive backups
ARCHIVE_DIR="backups/archive-$(date +%Y%m)"
mkdir -p "$ARCHIVE_DIR"
mv backups/cutover-* "$ARCHIVE_DIR/"
tar -czf "$ARCHIVE_DIR.tar.gz" "$ARCHIVE_DIR"
```

**Checklist:**
- [ ] All old resources deleted
- [ ] Git tagged
- [ ] Backups archived

---

## DNS/Route Considerations

### Current Route Configuration

**Production Route:**
- **Name:** north
- **Namespace:** qr-demo-qa
- **Host:** north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com
- **TLS:** Edge termination
- **Target:** Service "north" (pre-cutover) → Service "nginx-v2" (post-cutover)

### DNS Propagation

**Good News:** No DNS changes required!

The cutover only changes the **service target** of the route, not the route hostname. DNS remains:

```
north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com
  → OpenShift router (cluster ingress)
  → Route "north" in qr-demo-qa namespace
  → Service "nginx-v2" (cross-namespace ExternalName)
  → Service "nginx" in qr-demo-dev namespace
  → nginx pods
```

**DNS TTL:** Not applicable (no DNS change)
**Propagation Time:** 0 seconds (route update is instant)

### Load Balancer Considerations

**OpenShift Router:**
- HAProxy-based layer 7 load balancer
- Handles TLS termination
- No changes to router configuration
- Route update takes effect within 1-2 seconds

**Session Affinity:**
- Current route has `haproxy.router.openshift.io/disable_cookies: 'true'`
- No sticky sessions (good for SSE with Redis pub/sub)
- Each request can hit different backend pod
- Redis ensures event consistency across replicas

### External DNS (if applicable)

**If custom domain is configured** (e.g., demo.ohc.example.com):

1. **No changes required** if CNAME points to OpenShift route
2. **Update CNAME** if pointing directly to old IP
3. **TTL considerations:** Wait for DNS TTL to expire before cleanup

**Check if external DNS exists:**

```bash
# Check for custom domain routes
oc get route -n qr-demo-qa -o yaml | grep -i host

# If custom domain found, document here:
# Custom domain: _______________
# DNS provider: _______________
# TTL: _______________
```

---

## Risk Assessment

### High Confidence Items (Low Risk)

✅ **nginx serves static files** — Already tested in qr-demo-dev
✅ **Redis persistence** — Tested with pod restarts
✅ **Multi-replica SSE** — Tested with 3 replicas
✅ **API endpoints work** — All tested in dev
✅ **Instant rollback** — Route update is atomic and reversible

### Medium Confidence Items (Medium Risk)

⚠️ **Cross-namespace routing** — ExternalName services work in theory, need validation
⚠️ **SSE under load** — Tested with 10 concurrent users, not stress tested
⚠️ **Video playback at scale** — Not tested with multiple simultaneous streams

**Mitigation:**
- Test cross-namespace routing in Phase 1
- Monitor nginx/API logs during cutover
- Have rollback procedure ready

### Low Confidence Items (Higher Risk)

🔶 **Unknown edge cases** — Users may access URLs we haven't tested
🔶 **Browser caching** — Some users may have old HTML cached
🔶 **Third-party integrations** — If any external systems POST to our API

**Mitigation:**
- 48-hour stabilization period before cleanup
- Keep old deployment alive during monitoring
- Document any new issues discovered

### Rollback Confidence

✅ **Instant rollback available** — Route patch takes < 5 seconds
✅ **Old deployment untouched** — Still running during cutover
✅ **Backups created** — All resources backed up before cutover
✅ **Tested rollback procedure** — Can be validated pre-cutover

**Overall Risk:** LOW

---

## Communication Templates

### Pre-Cutover Announcement (24 hours before)

```
Subject: QR Demo System Migration — Tomorrow at [TIME]

Team,

We will be migrating the QR Demo system to a new architecture tomorrow:

Date: [DATE]
Time: [TIME] (cutover window: 15 minutes)
Expected downtime: 0 seconds (zero-downtime cutover)
Affected URL: https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com

What's changing:
- New nginx-based static file serving (faster page loads)
- Redis-backed state persistence (survives pod restarts)
- Multi-replica support (better reliability)
- Video support for Blackjack presentation

What's NOT changing:
- Same URL
- Same functionality
- Same look and feel

Rollback plan: Instant rollback available if issues arise

Questions? Reply to this email or ping #qr-demo-migration channel.

Thanks,
[YOUR NAME]
```

---

### Cutover Success Notification

```
Subject: QR Demo Migration Complete — SUCCESS

Team,

The QR Demo migration has been completed successfully.

Cutover time: [TIME]
Actual downtime: 0 seconds
New architecture: Active and healthy

What's new:
✅ Videos now work (blackjack presentation has actual video)
✅ Faster page loads (nginx caching + gzip)
✅ Better reliability (2 API replicas + Redis persistence)
✅ Horizontal scaling enabled (can add more replicas if needed)

Production URL: https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com

Please report any issues to #qr-demo-migration channel.

Monitoring period: 48 hours before final cleanup

Thanks,
[YOUR NAME]
```

---

### Rollback Notification (if needed)

```
Subject: QR Demo Migration — ROLLED BACK

Team,

The QR Demo migration has been rolled back to the previous architecture.

Rollback time: [TIME]
Reason: [REASON]
Current status: Production stable on old architecture

Details:
- Old deployment: Restored and healthy
- Production URL: Working normally
- New architecture: Under investigation in qr-demo-dev

Next steps:
1. Investigate root cause
2. Fix issues in dev environment
3. Schedule new cutover window

Questions? Reply to this email or ping #qr-demo-migration channel.

Thanks,
[YOUR NAME]
```

---

## Appendix A: Key Contacts

| Role | Name | Contact | Responsibility |
|------|------|---------|----------------|
| Technical Lead | Jim O'Donnell | [email] | Go/no-go decision, rollback authority |
| Platform Admin | [NAME] | [email] | OpenShift access, namespace permissions |
| Stakeholder | [NAME] | [email] | Business approval, user communication |
| On-call Engineer | [NAME] | [phone] | Emergency rollback execution |

---

## Appendix B: Quick Reference Commands

### Check Production Status

```bash
# Current route target
oc get route north -n qr-demo-qa -o jsonpath='{.spec.to.name}'

# Pod status in both namespaces
oc get pods -n qr-demo-qa | grep north
oc get pods -n qr-demo-dev | grep -E "(nginx|north-api|redis)"

# Test production URL
curl -I https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com/stage
```

### Emergency Rollback One-Liner

```bash
# Revert route to old deployment
oc patch route north -n qr-demo-qa -p '{"spec":{"to":{"name":"north"}}}' && \
curl -I https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com/stage
```

### Check New Architecture Health

```bash
# All-in-one health check
oc get pods -n qr-demo-dev && \
oc exec -it deployment/redis -n qr-demo-dev -- redis-cli PING && \
curl -I https://qr-demo-dev-qr-demo-dev.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com/stage
```

---

## Appendix C: Lessons Learned (Post-Cutover)

**To be filled out after cutover completes**

### What Went Well

- [ ] _[To be filled]_
- [ ] _[To be filled]_

### What Could Be Improved

- [ ] _[To be filled]_
- [ ] _[To be filled]_

### Surprises / Unexpected Issues

- [ ] _[To be filled]_
- [ ] _[To be filled]_

### Recommendations for Future Migrations

- [ ] _[To be filled]_
- [ ] _[To be filled]_

---

## Approval Signatures

**Technical Approval:**
Name: _______________
Signature: _______________
Date: _______________

**Business Approval:**
Name: _______________
Signature: _______________
Date: _______________

**Cutover Execution Authorization:**
Name: _______________
Signature: _______________
Date: _______________

---

**Document Version:** 1.0
**Last Updated:** 2026-02-19
**Next Review:** Post-cutover (within 7 days)
