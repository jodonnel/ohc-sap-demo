#!/bin/bash
set -euo pipefail
INPUT="$1"

# 1. Reject Lowercase Keys (Quadlet keys are PascalCase)
grep -Eq '^[a-z][A-Za-z0-9]*=' "$INPUT" && { echo "ERROR: Lowercase keys are invalid" >&2; exit 1; }

# 2. Reject Forbidden Docker-isms (Case-insensitive)
grep -Eqi 'user=|group=|command=|port-map=|networks=' "$INPUT" && { 
  echo "ERROR: Invalid keys. Use 'Exec=' not 'Command=', and ensure Network is in [Service]" >&2
  exit 1 
}

# 3. Require Image Key (Minimal validity)
grep -q '^Image=' "$INPUT" || { echo "ERROR: Missing Image= key" >&2; exit 1; }

exit 0
