# Chloe Framework (local, portable, auditable)

Chloe is a lightweight “truth snapshot” + operational playbook for running one or more local AI assistants (and the human who wrangles them).

This repo is intentionally simple:
- **STATE/** is the canonical truth source (human-readable + machine-readable).
- **SCRIPTS/** are the repeatable operations (update state, harvest, compare, triage).
- **DIAG/** is disposable output (ignored by git).
- **RECOVERY/** is for “find the missing pieces” expeditions (ignored by git).

---

## Repository layout

### State (authoritative truth)
- `STATE/ENVIRONMENT.md`
  - Human-readable “what is this box?” snapshot: OS, kernel, GPU, CUDA, runtimes.
- `STATE/INVENTORY.yaml`
  - Structured version of the same truth for automation.
- `STATE/MAILBOX.md`
  - Append-only breadcrumbs (decisions, actions, important notes).
- `STATE/GROUNDING.md`
  - Chloe’s grounding / principles / stewardship (the “why”).
- `STATE/SOP_UPDATE_STATE.md`
  - How to refresh state and what it means.
- `STATE/TODO.md`, `STATE/RISKLOG.md`, `STATE/CHANGELOG.md`
  - Lightweight lifecycle management: plans, risks, and what changed.

### Scripts (repeatable operations)
- `SCRIPTS/update_state.sh`
  - Canonical updater that regenerates `ENVIRONMENT.md` + `INVENTORY.yaml`
  - Also drops a mailbox breadcrumb so other Chloes can see what happened.
- `SCRIPTS/harvest_selective.sh`
  - Collects a selective “context bundle” into `DIAG/reports/`.
- `SCRIPTS/compare_three.sh`
  - Asks multiple local models the same prompt and scores responses.

---

## Quick start (the 3 commands you’ll run constantly)

### 1) Refresh Chloe truth on this host
```bash
~/chloe/SCRIPTS/update_state.sh
```

### 2) Add a mailbox note (breadcrumb)
Add this helper function to your shell (see `STATE/MAILBOX.md` too):

```bash
chloe_mail () { echo "- $(date -u +'%Y-%m-%dT%H:%M:%SZ') [${1:-note}]: ${2:-(no message)}" >> $HOME/chloe/STATE/MAILBOX.md; tail -n 5 $HOME/chloe/STATE/MAILBOX.md; }
```

Then use it:
```bash
chloe_mail note "did the thing; it worked"
```

### 3) Generate a selective harvest report
```bash
~/chloe/SCRIPTS/harvest_selective.sh "$HOME"
```

---

## Conventions (so future Chloes don’t get confused)

- **UTC timestamps only** (avoid timezone drift across machines).
- **STATE is authoritative**: if it’s not in `STATE/`, it’s a rumor.
- Prefer **best-effort scripts**: missing optional tools should not crash the updater.
- **No secrets in git**: tokens/keys belong outside this repo and are ignored by `.gitignore`.

---

## Roadmap (high level)

- Add a `bootstrap_host.sh` for new hosts (deps + directories + smoke tests).
- Add optional **user-level systemd services** for local model servers (reliability).
- Add a **bundle + checksum export** for sharing Chloe state between machines.
