# Production Cutover Checklist — Quick Reference

**Date:** 2026-02-19
**Status:** READY FOR EXECUTION
**Full Plan:** See [CUTOVER-PLAN.md](./CUTOVER-PLAN.md)

---

## Pre-Flight Checklist (Day Before)

### Validation in qr-demo-dev

- [ ] Dashboard loads: https://qr-demo-dev-qr-demo-dev.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com/stage
- [ ] SSE stream works (open dashboard, fire event)
- [ ] All 15 presentation decks load
- [ ] Blackjack video plays (disclaimer.mp4)
- [ ] Multi-replica test passed (scale to 3, test SSE sync)
- [ ] Redis persistence tested (restart pod, verify state)

### Backups Created

```bash
BACKUP_DIR="backups/cutover-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
oc get deployment north -n qr-demo-qa -o yaml > "$BACKUP_DIR/north-deployment.yaml"
oc get service north -n qr-demo-qa -o yaml > "$BACKUP_DIR/north-service.yaml"
oc get route north -n qr-demo-qa -o yaml > "$BACKUP_DIR/north-route.yaml"
oc get configmap north-app -n qr-demo-qa -o yaml > "$BACKUP_DIR/north-app-configmap.yaml"
oc get configmap north-stage-dashboard -n qr-demo-qa -o yaml > "$BACKUP_DIR/north-stage-dashboard-configmap.yaml"
git tag -a "pre-cutover-$(date +%Y%m%d-%H%M%S)" -m "Pre-cutover snapshot"
git push origin --tags
```

- [ ] Backup files created in `backups/cutover-YYYYMMDD-HHMMSS/`
- [ ] Git tag created and pushed
- [ ] Backup files verified readable

### Communication

- [ ] Stakeholders notified (24h advance notice)
- [ ] War room channel created
- [ ] Rollback authority designated

---

## Cutover Execution (15 minutes)

### Phase 1: Setup Cross-Namespace Routing (10 min)

#### 1.1 Create ExternalName Service

```bash
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
```

- [ ] Service nginx-v2 created in qr-demo-qa

#### 1.2 Create Test Route

```bash
cat <<EOF | oc apply -f -
apiVersion: route.openshift.io/v1
kind: Route
metadata:
  name: north-v2-test
  namespace: qr-demo-qa
  annotations:
    haproxy.router.openshift.io/balance: roundrobin
    haproxy.router.openshift.io/disable_cookies: 'true'
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
EOF

TEST_URL=$(oc get route north-v2-test -n qr-demo-qa -o jsonpath='{.spec.host}')
echo "Test URL: https://$TEST_URL"
```

- [ ] Test route created
- [ ] Test URL printed

#### 1.3 Validate Test Route

```bash
curl -I https://$TEST_URL/stage                    # Expected: 200 OK
curl -N https://$TEST_URL/events | head -n 3       # Expected: SSE stream
curl -X POST https://$TEST_URL/badge/tap \
  -H "Content-Type: application/json" \
  -d '{"badge_id":"test","action":"tap"}'          # Expected: {"status":"ok"}
```

- [ ] Dashboard: 200 OK
- [ ] SSE stream: Working
- [ ] API POST: 200 OK

**STOP HERE IF TEST ROUTE FAILS**

---

### Phase 2: Production Cutover (5 min)

#### 2.1 Final Pre-Cutover Checks

```bash
curl -I https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com/stage
curl -I https://$TEST_URL/stage
oc get pods -n qr-demo-dev | grep -v Running | grep -v Completed
oc exec -it deployment/redis -n qr-demo-dev -- redis-cli PING
```

- [ ] Old production: 200 OK
- [ ] New test route: 200 OK
- [ ] All pods: Running
- [ ] Redis: PONG

#### 2.2 Save Route State & Execute Cutover

```bash
# Save current state
oc get route north -n qr-demo-qa -o yaml > /tmp/north-route-before-cutover.yaml

# CUTOVER - Update production route
oc patch route north -n qr-demo-qa -p '{
  "spec": {
    "to": {
      "name": "nginx-v2"
    }
  }
}'

# Record timestamp
echo "Cutover at: $(date -Iseconds)" | tee /tmp/cutover-timestamp.txt
```

- [ ] Route state saved
- [ ] Production route updated
- [ ] Timestamp recorded

#### 2.3 Immediate Validation (< 60 sec)

```bash
sleep 5

# Test production now points to new architecture
curl -I https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com/stage

# Check for nginx headers
curl -I https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com/stage | grep -i "Server: nginx"

# Test SSE
curl -N https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com/events &
CURL_PID=$!
sleep 2
kill $CURL_PID

# Fire test event
curl -X POST https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com/badge/tap \
  -H "Content-Type: application/json" \
  -d '{"badge_id":"cutover-test","action":"tap"}'
```

- [ ] Dashboard: 200 OK
- [ ] Server header: nginx
- [ ] SSE stream: Working
- [ ] API POST: 200 OK

**DECISION POINT:**
- ✅ **All checks pass:** Continue to monitoring
- ❌ **Any check fails:** EXECUTE ROLLBACK (see below)

---

## Emergency Rollback (< 2 min)

### One-Liner Rollback

```bash
oc apply -f /tmp/north-route-before-cutover.yaml
```

**OR** (if backup file lost):

```bash
oc patch route north -n qr-demo-qa -p '{"spec":{"to":{"name":"north"}}}'
```

### Validate Rollback

```bash
curl -I https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com/stage
oc get pods -n qr-demo-qa | grep north
```

- [ ] Old production: 200 OK
- [ ] Old deployment: Running
- [ ] Dashboard loads

---

## Post-Cutover Monitoring (30 min)

### Watch Logs (4 terminals)

```bash
# Terminal 1
oc logs -f deployment/nginx -n qr-demo-dev

# Terminal 2
oc logs -f deployment/north-api -n qr-demo-dev --all-containers=true

# Terminal 3
oc logs -f deployment/redis -n qr-demo-dev

# Terminal 4
watch -n 2 'oc get pods -n qr-demo-dev'
```

- [ ] No 500 errors in nginx
- [ ] No Python exceptions in Flask
- [ ] No Redis connection errors
- [ ] No pod restarts

### User Acceptance Testing

Open: https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com/stage

- [ ] Dashboard loads
- [ ] SSE stream shows updates
- [ ] Fire event from /play
- [ ] Event appears instantly
- [ ] Load 3-4 presentation decks
- [ ] Play blackjack video
- [ ] Check browser console (no errors)

### Load Test

```bash
for i in {1..50}; do
  curl -X POST https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com/badge/tap \
    -H "Content-Type: application/json" \
    -d "{\"badge_id\":\"load-test-$i\",\"action\":\"tap\"}" &
done
wait
```

- [ ] All 50 events processed
- [ ] No errors in logs
- [ ] Dashboard shows all events

---

## Post-Cutover Checklist

### Immediate (T+0 to T+1 hour)

- [ ] All validation tests passed
- [ ] No errors in logs
- [ ] Stakeholders notified of success
- [ ] Monitoring dashboards updated

### T+6 hours

- [ ] Run automated test suite
- [ ] Check error rates
- [ ] Verify no user complaints

### T+24 hours

- [ ] Run automated test suite
- [ ] Review logs for patterns
- [ ] Test Redis persistence (restart pod)

### T+48 hours

- [ ] Run automated test suite
- [ ] Final go/no-go for cleanup
- [ ] If stable, proceed to cleanup

---

## Cleanup (Day 3+)

### Remove Old Deployment

```bash
# Verify new architecture healthy
./scripts/post-cutover-tests.sh

# Delete old resources
oc delete deployment north -n qr-demo-qa
oc delete configmap north-app -n qr-demo-qa
oc delete configmap north-stage-dashboard -n qr-demo-qa
oc delete configmap north-assets -n qr-demo-qa
oc delete route north-v2-test -n qr-demo-qa
```

- [ ] Old deployment deleted
- [ ] Old ConfigMaps deleted
- [ ] Test route deleted
- [ ] Production still working

---

## Quick Reference URLs

### Production

- **Old (pre-cutover):** https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com
- **New (post-cutover):** Same URL, different backend

### Testing

- **Dev environment:** https://qr-demo-dev-qr-demo-dev.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com
- **Test route (during cutover):** https://north-v2-test-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com

---

## Emergency Contacts

| Role | Name | Contact |
|------|------|---------|
| Technical Lead | Jim O'Donnell | [FILL IN] |
| Rollback Authority | [FILL IN] | [FILL IN] |
| On-call Engineer | [FILL IN] | [FILL IN] |

---

## Notes / Issues During Cutover

**Use this space to document any issues encountered:**

```
Time: ______
Issue: ______
Resolution: ______

Time: ______
Issue: ______
Resolution: ______
```

---

**Last Updated:** 2026-02-19
**Full Plan:** [CUTOVER-PLAN.md](./CUTOVER-PLAN.md)
