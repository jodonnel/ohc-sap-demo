# Cutover Documentation — Quick Start

This directory contains comprehensive documentation for the production cutover from the old ConfigMap-based architecture to the new nginx+Redis+Flask architecture.

---

## Documents

### 1. [CUTOVER-PLAN.md](./CUTOVER-PLAN.md) — Full Detailed Plan (15,000+ words)

**Comprehensive cutover plan with:**
- Executive summary
- Pre-cutover validation checklist
- Three cutover options analyzed (Route Update, Blue/Green, In-Place)
- Step-by-step procedures with rollback points
- Emergency rollback procedures (< 2 min)
- Post-cutover validation tests
- 48-hour monitoring plan
- Cleanup procedures
- Risk assessment
- Communication templates

**Use this for:**
- Planning and approval
- Understanding all cutover options
- Detailed rollback procedures
- Post-cutover monitoring strategy

---

### 2. [CUTOVER-CHECKLIST.md](./CUTOVER-CHECKLIST.md) — Day-of Execution Guide

**Quick reference checklist for cutover day:**
- Pre-flight validation (day before)
- Backup creation commands
- Step-by-step cutover execution (15 min)
- Emergency rollback one-liners
- Post-cutover monitoring checklist
- Cleanup tasks (day 3+)

**Use this for:**
- Actual cutover execution
- Real-time reference during cutover
- Quick rollback commands
- Post-cutover validation

---

### 3. [REBUILD-PLAN.md](./REBUILD-PLAN.md) — Architecture Design

**Why rebuild, proposed architecture, deployment strategy:**
- Problems with current ConfigMap approach
- New nginx+Redis+Flask architecture diagrams
- Zero-downtime deployment strategy
- File structure after rebuild
- Timeline (3-4 hours, 0 downtime)

**Use this for:**
- Understanding the "why" behind the migration
- Architecture reference
- Stakeholder approval

---

### 4. [CURRENT-STATE.md](./CURRENT-STATE.md) — Current Production

**Documentation of existing production system:**
- Current architecture (ConfigMap-based)
- What's deployed and working
- Known issues and limitations
- Current deployment workflow
- Backup snapshot information

**Use this for:**
- Understanding current state
- Baseline before cutover
- Rollback reference

---

## Scripts

### 1. `/scripts/post-cutover-tests.sh` — Automated Test Suite

**Comprehensive validation tests:**
- Dashboard, SSE stream, API endpoints
- All 15 presentation decks
- Video files (blackjack)
- Scenario endpoints
- Multi-replica health
- Redis persistence

**Usage:**
```bash
# Test production
./scripts/post-cutover-tests.sh

# Test dev environment
./scripts/post-cutover-tests.sh https://qr-demo-dev-qr-demo-dev.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com
```

**Run this:**
- Before cutover (validate qr-demo-dev)
- Immediately after cutover
- T+1 hour, T+6 hours, T+24 hours, T+48 hours

---

### 2. `/scripts/health-check.sh` — Quick Health Check

**Lightweight health monitoring:**
- Dashboard status
- SSE stream
- API endpoint
- Server type (nginx vs Flask)
- Pod status
- Redis health
- Current route target

**Usage:**
```bash
./scripts/health-check.sh
```

**Run this:**
- Every 6 hours during 48-hour stabilization
- On-demand for quick status check

---

### 3. `/scripts/emergency-rollback.sh` — Emergency Rollback

**One-command rollback to old architecture:**
- Confirms before execution
- Uses backup file if available
- Falls back to manual patch
- Verifies rollback success
- Creates rollback report

**Usage:**
```bash
./scripts/emergency-rollback.sh
# Type 'ROLLBACK' to confirm
```

**Use this when:**
- Cutover fails validation
- Critical issues discovered post-cutover
- Need immediate revert to old architecture

---

## Quick Reference

### Current Production

**URL:** https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com

**Old Architecture (pre-cutover):**
- Namespace: qr-demo-qa
- Service: north
- Backend: Flask (ConfigMap-based)
- State: In-memory (Python dicts)

**New Architecture (post-cutover):**
- Namespace: qr-demo-dev (backends running here)
- Service: nginx-v2 (ExternalName pointing to qr-demo-dev)
- Backend: nginx + Redis + Flask
- State: Redis (persistent)

---

### Dev Environment (Testing)

**URL:** https://qr-demo-dev-qr-demo-dev.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com

**Architecture:**
- Namespace: qr-demo-dev
- Service: nginx
- Pods: nginx (1), north-api (2), redis (1)
- State: Redis with persistent volume

---

### Cutover Timeline

| Time | Activity | Script |
|------|----------|--------|
| **Day -1** | Validate qr-demo-dev | `./scripts/post-cutover-tests.sh [dev-url]` |
| **Day -1** | Create backups | Commands in CUTOVER-CHECKLIST.md |
| **Day 0** | Execute cutover | CUTOVER-CHECKLIST.md (15 min) |
| **Day 0 (T+0)** | Immediate validation | `./scripts/post-cutover-tests.sh` |
| **Day 0 (T+1h)** | Health check | `./scripts/health-check.sh` |
| **Day 0 (T+6h)** | Health check | `./scripts/health-check.sh` |
| **Day 1 (T+24h)** | Full test suite | `./scripts/post-cutover-tests.sh` |
| **Day 2 (T+48h)** | Final validation | `./scripts/post-cutover-tests.sh` |
| **Day 3** | Cleanup (if stable) | Commands in CUTOVER-CHECKLIST.md |

---

### Emergency Commands

**Check route target:**
```bash
oc get route north -n qr-demo-qa -o jsonpath='{.spec.to.name}'
```

**Rollback (manual):**
```bash
oc patch route north -n qr-demo-qa -p '{"spec":{"to":{"name":"north"}}}'
```

**Rollback (automated):**
```bash
./scripts/emergency-rollback.sh
```

**Test production:**
```bash
curl -I https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com/stage
```

**Check pods:**
```bash
oc get pods -n qr-demo-dev | grep -E "(nginx|north-api|redis)"
```

---

### Decision Tree

**Pre-Cutover:**
1. Read [CUTOVER-PLAN.md](./CUTOVER-PLAN.md) for full context
2. Review [REBUILD-PLAN.md](./REBUILD-PLAN.md) for architecture
3. Use [CUTOVER-CHECKLIST.md](./CUTOVER-CHECKLIST.md) for execution

**During Cutover:**
1. Follow [CUTOVER-CHECKLIST.md](./CUTOVER-CHECKLIST.md) step-by-step
2. Run `./scripts/post-cutover-tests.sh` immediately after
3. If tests fail: run `./scripts/emergency-rollback.sh`

**Post-Cutover:**
1. Run `./scripts/health-check.sh` every 6 hours
2. Run `./scripts/post-cutover-tests.sh` at T+24h and T+48h
3. If stable at T+48h: proceed with cleanup

**Rollback Scenarios:**
- **Immediate (< 5 min):** Use backup file or manual patch
- **Delayed (< 24h):** Restore from backup, may need to redeploy
- **Emergency:** Run `./scripts/emergency-rollback.sh`

---

## File Locations

```
ohc-sap-demo/
├── docs/
│   └── architecture/
│       ├── CUTOVER-README.md          # This file
│       ├── CUTOVER-PLAN.md            # Full detailed plan (15k+ words)
│       ├── CUTOVER-CHECKLIST.md       # Day-of execution checklist
│       ├── REBUILD-PLAN.md            # Architecture design doc
│       └── CURRENT-STATE.md           # Current production state
├── scripts/
│   ├── post-cutover-tests.sh          # Automated test suite
│   ├── health-check.sh                # Quick health check
│   └── emergency-rollback.sh          # Emergency rollback script
└── backups/
    └── cutover-YYYYMMDD-HHMMSS/       # Created during cutover
        ├── north-deployment.yaml
        ├── north-service.yaml
        ├── north-route.yaml
        └── north-*-configmap.yaml
```

---

## Next Steps

1. **For Approval:** Read [CUTOVER-PLAN.md](./CUTOVER-PLAN.md)
2. **For Execution:** Use [CUTOVER-CHECKLIST.md](./CUTOVER-CHECKLIST.md)
3. **For Testing:** Run `./scripts/post-cutover-tests.sh`
4. **For Monitoring:** Run `./scripts/health-check.sh`
5. **For Rollback:** Run `./scripts/emergency-rollback.sh`

---

**Last Updated:** 2026-02-19
**Maintained By:** CC (Claude Code) + Jim O'Donnell
**Status:** Ready for execution
