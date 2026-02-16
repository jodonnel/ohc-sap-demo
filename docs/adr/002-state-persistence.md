# ADR-002: Persistent state via PVC JSON flush

**Date:** 2026-02-16
**Status:** Accepted
**Deciders:** Jim O'Donnell, Chloe (architect), Claude Code, Claude Web

## Context

The Flask app stored all state (event count, telemetry, event log) in memory. Any pod restart — voluntary (rollout) or involuntary (OOM, node drain) — reset the demo to zero. During a live presentation, losing 300+ events mid-demo is unacceptable.

Options considered:

- **A. Redis/PostgreSQL sidecar** — heavy for a demo, adds operational complexity
- **B. etcd or ConfigMap writes** — fragile, not designed for frequent writes
- **C. Periodic JSON flush to PVC** — simple, reliable, no new dependencies

## Decision

Option C: flush state to `/data/state.json` on a 1Gi `ReadWriteOnce` PVC.

- Daemon thread flushes every 10 seconds (configurable via `FLUSH_INTERVAL`)
- Atomic write: write to `.tmp`, then `os.replace()`
- `SIGTERM` handler + `atexit` for graceful shutdown flush
- `load_state()` on startup restores from the JSON file
- `POST /reset` clears state and deletes the file

## Consequences

**Positive:**
- Demo survives pod restarts (verified: 347 events survived a rollout)
- Zero new dependencies
- State file is human-readable JSON (debuggable)

**Negative:**
- Up to 10 seconds of data loss on ungraceful kill (`SIGKILL`)
- `ReadWriteOnce` means no horizontal scaling (acceptable for single-replica demo)
- PVC lifecycle tied to namespace (acceptable — sandbox is ephemeral anyway)
