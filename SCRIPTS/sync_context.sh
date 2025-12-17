#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE="$ROOT/STATE"

echo "== chloe sync_context =="
echo "repo: $ROOT"
echo "time: $(date -Is)"
echo

# Prefer your existing state_union if present
if [[ -x "$ROOT/SCRIPTS/state_union.sh" ]]; then
  echo "== state_union.sh =="
  "$ROOT/SCRIPTS/state_union.sh" 2>/dev/null || true
  echo
fi

echo "== BOOTSTRAP.md (tail) =="
if [[ -f "$STATE/BOOTSTRAP.md" ]]; then
  tail -n 120 "$STATE/BOOTSTRAP.md"
else
  echo "(missing) $STATE/BOOTSTRAP.md"
fi
echo

echo "== ENVIRONMENT.md (tail) =="
if [[ -f "$STATE/ENVIRONMENT.md" ]]; then
  tail -n 120 "$STATE/ENVIRONMENT.md"
else
  echo "(missing) $STATE/ENVIRONMENT.md"
fi
echo

echo "== INVENTORY.yaml =="
if [[ -f "$STATE/INVENTORY.yaml" ]]; then
  sed -n '1,220p' "$STATE/INVENTORY.yaml"
else
  echo "(missing) $STATE/INVENTORY.yaml"
fi
echo

echo "== MAILBOX.md (tail) =="
if [[ -f "$STATE/MAILBOX.md" ]]; then
  tail -n 120 "$STATE/MAILBOX.md"
else
  echo "(missing) $STATE/MAILBOX.md"
fi
echo

echo "== CHANGELOG.md (tail) =="
if [[ -f "$STATE/CHANGELOG.md" ]]; then
  tail -n 120 "$STATE/CHANGELOG.md"
else
  echo "(missing) $STATE/CHANGELOG.md"
fi
