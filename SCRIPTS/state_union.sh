#!/usr/bin/env bash
#===============================================================================
# Chloe State of the Union — single-file, bot-ingestible truth bundle
#
# Usage:
#   cd ~/chloe && ./SCRIPTS/state_union.sh
#
# Output:
#   STATE/STATE_OF_UNION.txt
#
# Behavior:
#   1) Runs ./SCRIPTS/update_state.sh to refresh canonical state
#   2) Writes one ordered blob with clear sentinels + sections + optional git info
#===============================================================================

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# 1) Refresh canonical state first (authoritative truth step)
./SCRIPTS/update_state.sh

OUT="$ROOT/STATE/STATE_OF_UNION.txt"
NOW="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
HOST="$(hostname 2>/dev/null || echo unknown)"

# 2) Build deterministic, ingestible blob
{
  echo "=== CHLOE STATE OF UNION BEGIN ==="
  echo "timestamp_utc: $NOW"
  echo "host: $HOST"
  echo "repo_root: $ROOT"
  echo

  echo "----- STATE/ENVIRONMENT.md -----"
  if [ -f STATE/ENVIRONMENT.md ]; then
    cat STATE/ENVIRONMENT.md
  else
    echo "(missing)"
  fi
  echo

  echo "----- STATE/INVENTORY.yaml -----"
  if [ -f STATE/INVENTORY.yaml ]; then
    cat STATE/INVENTORY.yaml
  else
    echo "(missing)"
  fi
  echo

  echo "----- STATE/CHANGELOG.md (head 200) -----"
  if [ -f STATE/CHANGELOG.md ]; then
    sed -n '1,200p' STATE/CHANGELOG.md
  else
    echo "(missing)"
  fi
  echo

  echo "----- STATE/MAILBOX.md (tail 200) -----"
  if [ -f STATE/MAILBOX.md ]; then
    tail -n 200 STATE/MAILBOX.md
  else
    echo "(missing)"
  fi
  echo

  echo "----- GIT CONTEXT -----"
  if command -v git >/dev/null 2>&1 && [ -d .git ]; then
    echo "git_head: $(git rev-parse HEAD 2>/dev/null || echo unknown)"
    echo "git_branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
    echo "git_status:"
    git status --porcelain 2>/dev/null || true
  else
    echo "(git not available or not a git repo)"
  fi
  echo

  echo "----- CHECKSUMS -----"
  if command -v sha256sum >/dev/null 2>&1; then
    for f in STATE/ENVIRONMENT.md STATE/INVENTORY.yaml STATE/CHANGELOG.md STATE/MAILBOX.md; do
      [ -f "$f" ] && sha256sum "$f" || true
    done
  else
    echo "(sha256sum not available)"
  fi
  echo

  echo "=== CHLOE STATE OF UNION END ==="
} > "$OUT"

echo "OK: wrote $OUT"
