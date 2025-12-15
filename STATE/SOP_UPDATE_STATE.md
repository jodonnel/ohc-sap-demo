# SOP: Updating Chloe State

## What this does
Running `SCRIPTS/update_state.sh` refreshes the **canonical host snapshot**:

- `STATE/ENVIRONMENT.md` (human-readable)
- `STATE/INVENTORY.yaml` (structured)
- appends a breadcrumb to `STATE/MAILBOX.md` (audit trail)

This is the official “tell the truth” command for Chloe environments.

## When to run it
Run it whenever you change anything environment-related, especially:

- kernel / OS updates
- NVIDIA driver changes
- CUDA toolkit/runtime changes
- installing/removing ML Python packages
- changing container runtime setup

## Command
From `~/chloe`:

```bash
./SCRIPTS/update_state.sh
```

Optionally attach a harvest report path (provenance only):

```bash
./SCRIPTS/update_state.sh "$HOME/chloe/DIAG/reports/selective_<timestamp>.txt"
```

## Teaching other Chloes
“Other Chloes” should treat these files as the source of truth:

1. Read `STATE/ENVIRONMENT.md` for narrative understanding.
2. Parse `STATE/INVENTORY.yaml` if you need structured decisions.
3. Check `STATE/MAILBOX.md` for what changed recently.

If a Chloe suspects drift, the remedy is always:
`./SCRIPTS/update_state.sh`
