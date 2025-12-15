#!/usr/bin/env bash
#===============================================================================
# Chloe State Updater — canonical "truth snapshot" generator
#
# PURPOSE
# -------
# This script is the canonical way to refresh Chloe’s state files on a host:
#
#   - STATE/ENVIRONMENT.md   (human-readable snapshot for Jim + other Chloes)
#   - STATE/INVENTORY.yaml   (structured snapshot for scripts/automation)
#   - STATE/MAILBOX.md       (append-only audit trail / breadcrumbs)
#   - STATE/SOP_UPDATE_STATE.md (how to teach/use this updater)
#
# Why we care:
#   - We do a lot of iterative debugging and environment drift is constant.
#   - Multiple “Chloe” contexts exist, and they need one consistent truth source.
#   - We want an easy one-liner to “re-sync reality” after changes.
#
# PRINCIPLES
# ----------
#   - Minimal dependencies: bash + python3 only.
#   - Best-effort: missing optional tools (docker, nvcc, etc.) should not break it.
#   - Deterministic outputs: always overwrite ENVIRONMENT.md + INVENTORY.yaml.
#   - Always leave a mailbox breadcrumb that captures *what ran when*.
#
# USAGE
# -----
#   ~/chloe/SCRIPTS/update_state.sh [optional_report_path]
#
# Examples:
#   ~/chloe/SCRIPTS/update_state.sh
#   ~/chloe/SCRIPTS/update_state.sh "$HOME/chloe/DIAG/reports/selective_2025-12-15T18:39:06Z.txt"
#
# Notes:
#   - optional_report_path is just provenance (a “source report” reference).
#   - the snapshots are generated from the live system, not parsed from the report.
#
#===============================================================================

set -euo pipefail

#------------------------------------------------------------------------------
# Repo root: script lives at ~/chloe/SCRIPTS, root is one directory up.
# We avoid git dependency; this works even if ~/chloe is not a git repo.
#------------------------------------------------------------------------------
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

#------------------------------------------------------------------------------
# Timestamp: always UTC to avoid timezone confusion when comparing machines/logs.
#------------------------------------------------------------------------------
NOW="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"

# Optional “source report” (e.g., a previous harvest output path).
REPORT="${1:-}"

# Ensure state directory exists (safe if already present).
mkdir -p "$ROOT/STATE"

#------------------------------------------------------------------------------
# Helper: check if command exists in PATH.
#------------------------------------------------------------------------------
have() { command -v "$1" >/dev/null 2>&1; }

#------------------------------------------------------------------------------
# 0) Gather system facts (best-effort)
#    We gather once, then write to multiple outputs.
#------------------------------------------------------------------------------
OS_PRETTY="unknown"
OS_VERSION_ID="unknown"
KERNEL_UNAME="$(uname -a 2>/dev/null || echo unknown)"

if [ -f /etc/os-release ]; then
  # shellcheck disable=SC1091
  . /etc/os-release
  OS_PRETTY="${PRETTY_NAME:-unknown}"
  OS_VERSION_ID="${VERSION_ID:-unknown}"
fi

GPU_MODEL="not-detected"
GPU_VRAM="not-detected"
NVIDIA_DRIVER="not-detected"
CUDA_RUNTIME="not-detected"
GPU_MEM_USED_MI="not-detected"

if have nvidia-smi; then
  GPU_MODEL="$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -n1 || echo unknown)"
  GPU_VRAM="$(nvidia-smi --query-gpu=memory.total --format=csv,noheader 2>/dev/null | head -n1 || echo unknown)"
  NVIDIA_DRIVER="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -n1 || echo unknown)"
  CUDA_RUNTIME="$(nvidia-smi | awk '/CUDA Version/ {print $NF; exit}' 2>/dev/null || echo unknown)"
  GPU_MEM_USED_MI="$(nvidia-smi --query-gpu=memory.used --format=csv,noheader 2>/dev/null | head -n1 || echo unknown)"
fi

NVCC_VERSION="not-detected"
if have nvcc; then
  NVCC_VERSION="$(nvcc --version 2>/dev/null | awk -F, '/release/ {print $2}' | sed 's/^ *release *//;s/ *$//' | head -n1 || echo unknown)"
fi

PODMAN_VERSION="not-detected"
DOCKER_VERSION="not-detected"
if have podman; then PODMAN_VERSION="$(podman --version 2>/dev/null | awk '{print $3}' || echo unknown)"; fi
if have docker; then DOCKER_VERSION="$(docker --version 2>/dev/null | awk '{print $3}' | tr -d ',' || echo unknown)"; fi

PYTHON_VERSION="not-detected"
if have python3; then PYTHON_VERSION="$(python3 --version 2>/dev/null | awk '{print $2}' || echo unknown)"; fi

# Probe python ML packages (presence + versions) via embedded python.
# We keep this tiny and non-fatal: if python errors, we just mark as not-detected.
TORCH_VER="not-detected"
TORCH_CUDA="not-detected"
TORCH_CUDA_AVAIL="not-detected"

if have python3; then
  read -r TORCH_VER TORCH_CUDA TORCH_CUDA_AVAIL < <(python3 - <<'PY' 2>/dev/null || true
import importlib
torch_ver="not-detected"; torch_cuda="not-detected"; cuda_avail="not-detected"
try:
    torch=importlib.import_module("torch")
    torch_ver=getattr(torch,"__version__","?")
    torch_cuda=getattr(getattr(torch,"version",None),"cuda","?")
    try:
        cuda_avail=str(bool(torch.cuda.is_available()))
    except Exception:
        cuda_avail="?"
except Exception:
    pass
print(torch_ver, torch_cuda, cuda_avail)
PY
)
fi

#------------------------------------------------------------------------------
# 1) Write STATE/ENVIRONMENT.md (human-readable)
#------------------------------------------------------------------------------
ENV_MD="$ROOT/STATE/ENVIRONMENT.md"
{
  echo "# Environment Snapshot"
  echo "Last verified: ${NOW}"
  echo
  echo "## Source Report"
  echo "${REPORT:-<none>}"
  echo
  echo "## OS / Kernel"
  echo "- PRETTY_NAME: ${OS_PRETTY}"
  echo "- VERSION_ID: ${OS_VERSION_ID}"
  echo "- Kernel (uname -a): ${KERNEL_UNAME}"
  echo
  echo "## GPU / Driver / CUDA"
  echo "- GPU: ${GPU_MODEL}"
  echo "- VRAM (reported by nvidia-smi): ${GPU_VRAM}"
  echo "- NVIDIA driver: ${NVIDIA_DRIVER}"
  echo "- CUDA runtime (nvidia-smi): ${CUDA_RUNTIME}"
  echo "- CUDA toolkit (nvcc): ${NVCC_VERSION}"
  echo
  echo "## Containers"
  echo "- Podman: ${PODMAN_VERSION}"
  echo "- Docker: ${DOCKER_VERSION}"
  echo
  echo "## Python / ML Runtimes"
  echo "- Python: ${PYTHON_VERSION}"
  echo "- PyTorch: ${TORCH_VER}"
  echo "- torch CUDA: ${TORCH_CUDA}"
  echo "- torch cuda_available: ${TORCH_CUDA_AVAIL}"
  echo
  echo "## Notes"
  if [ "${GPU_MEM_USED_MI}" != "not-detected" ]; then
    echo "- GPU memory in use at capture time (rough): ${GPU_MEM_USED_MI}. Close heavy GUI apps before big runs."
  else
    echo "- nvidia-smi not detected; GPU headroom unknown."
  fi
  echo "- This file is GENERATED. Edit SCRIPTS/update_state.sh if you want to change content."
} > "$ENV_MD"

#------------------------------------------------------------------------------
# 2) Write STATE/INVENTORY.yaml (structured)
#
# Important:
#   - We avoid YAML libraries by writing “simple YAML” ourselves.
#   - Keep it stable and boring; this is for scripting and diffing.
#------------------------------------------------------------------------------
INV_YAML="$ROOT/STATE/INVENTORY.yaml"
{
  echo "timestamp: \"${NOW}\""
  echo "hosts:"
  echo "  - name: \"$(hostname 2>/dev/null || echo unknown)\""
  echo "    os: \"${OS_PRETTY}\""
  echo "    version: \"${OS_VERSION_ID}\""
  echo "    kernel: \"${KERNEL_UNAME}\""
  echo "gpus:"
  echo "  - model: \"${GPU_MODEL}\""
  # vram_gb: try to parse an integer from "8192 MiB" style outputs; fall back to null.
  python3 - <<PY 2>/dev/null || echo "    vram_gb: null"
import re
s=${GPU_VRAM@Q}
m=re.search(r'(\d+)', s)
if not m:
    print("    vram_gb: null")
else:
    mib=int(m.group(1))
    gb=round(mib/1024, 2)
    if float(gb).is_integer():
        print(f"    vram_gb: {int(gb)}")
    else:
        print(f"    vram_gb: {gb}")
PY
  echo "drivers:"
  echo "  nvidia_driver: \"${NVIDIA_DRIVER}\""
  echo "cuda:"
  echo "  toolkit: \"${NVCC_VERSION}\""
  echo "  runtime: \"${CUDA_RUNTIME}\""
  echo "runtimes:"
  echo "  podman: \"${PODMAN_VERSION}\""
  echo "  docker: \"${DOCKER_VERSION}\""
  echo "pyenvs:"
  echo "  - name: \"system\""
  echo "    python: \"${PYTHON_VERSION}\""
  echo "    torch: \"${TORCH_VER}\""
  echo "    torch_cuda: \"${TORCH_CUDA}\""
  echo "models: []"
  echo "services: []"
} > "$INV_YAML"

#------------------------------------------------------------------------------
# 3) Append to STATE/MAILBOX.md (audit trail)
#
# This is intentionally append-only:
#   - You can grep for a date/time and see what was updated
#   - You can see the source report used (if any)
#------------------------------------------------------------------------------
MAILBOX="$ROOT/STATE/MAILBOX.md"
if [ ! -f "$MAILBOX" ]; then
  cat > "$MAILBOX" <<'MD'
# Chloe Mailbox

## How to write
Add this helper to your shell:

  chloe_mail () { echo "- $(date -u +'%Y-%m-%dT%H:%M:%SZ') [${1:-note}]: ${2:-(no message)}" >> $HOME/chloe/STATE/MAILBOX.md; tail -n 5 $HOME/chloe/STATE/MAILBOX.md; }

## Recent
MD
fi

echo "- ${NOW} [state]: update_state.sh wrote ENVIRONMENT.md + INVENTORY.yaml (report: ${REPORT:-<none>})" >> "$MAILBOX"

#------------------------------------------------------------------------------
# 4) Write the teaching doc (SOP)
#------------------------------------------------------------------------------
SOP="$ROOT/STATE/SOP_UPDATE_STATE.md"
cat > "$SOP" <<'MD'
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
MD

chmod +x "$ROOT/SCRIPTS/update_state.sh"

#------------------------------------------------------------------------------
# Final console summary: keep it short but useful.
#------------------------------------------------------------------------------
echo "OK: wrote:"
echo "  - $ENV_MD"
echo "  - $INV_YAML"
echo "  - $SOP"
echo "OK: appended mailbox:"
echo "  - $MAILBOX"
BASH
