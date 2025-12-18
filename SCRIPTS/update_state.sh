#!/usr/bin/env bash
set -euo pipefail

#------------------------------------------------------------------------------
# Chloe: update_state.sh
# Writes:
#   - STATE/ENVIRONMENT.md
#   - STATE/INVENTORY.yaml
#   - STATE/SOP_UPDATE_STATE.md
# Appends:
#   - STATE/MAILBOX.md
#------------------------------------------------------------------------------

have() { command -v "$1" >/dev/null 2>&1; }

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
STATE_DIR="${ROOT}/STATE"
mkdir -p "${STATE_DIR}"

NOW_UTC="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
HOSTNAME_SHORT="$(hostname -s 2>/dev/null || hostname 2>/dev/null || echo unknown)"

#------------------------------------------------------------------------------
# OS / Kernel
#------------------------------------------------------------------------------
OS_PRETTY="unknown"
VERSION_ID="unknown"
if [ -r /etc/os-release ]; then
  # shellcheck disable=SC1091
  . /etc/os-release
  OS_PRETTY="${PRETTY_NAME:-unknown}"
  VERSION_ID="${VERSION_ID:-unknown}"
fi
KERNEL_UNAME="$(uname -a 2>/dev/null || echo unknown)"

#------------------------------------------------------------------------------
# GPU / Driver / CUDA (nvidia-smi is authoritative for runtime)
#------------------------------------------------------------------------------
GPU_MODEL="not-detected"
GPU_VRAM_MI="not-detected"
NVIDIA_DRIVER="not-detected"
CUDA_RUNTIME="not-reported"

if have nvidia-smi; then
  GPU_MODEL="$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -n1 | sed 's/[[:space:]]*$//' || true)"
  [ -n "${GPU_MODEL}" ] || GPU_MODEL="unknown"

  GPU_VRAM_MI="$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -n1 | sed 's/[[:space:]]*$//' || true)"
  [ -n "${GPU_VRAM_MI}" ] || GPU_VRAM_MI="unknown"

  NVIDIA_DRIVER="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -n1 | sed 's/[[:space:]]*$//' || true)"
  [ -n "${NVIDIA_DRIVER}" ] || NVIDIA_DRIVER="unknown"

  CUDA_RUNTIME="$(nvidia-smi 2>/dev/null | sed -n 's/.*CUDA Version:[[:space:]]*\([0-9][0-9.]*\).*/\1/p' | head -n 1 | tr -d '\r\n')"
  [ -n "${CUDA_RUNTIME}" ] || CUDA_RUNTIME="not-reported"
fi

#------------------------------------------------------------------------------
# CUDA toolkit (nvcc)
#------------------------------------------------------------------------------
NVCC_VERSION="not-detected"

_nvcc_path=""
if have nvcc; then
  _nvcc_path="$(command -v nvcc)"
else
  # common locations + "latest" cuda-* if present
  if [ -x /usr/local/cuda/bin/nvcc ]; then
    _nvcc_path="/usr/local/cuda/bin/nvcc"
  else
    _nvcc_path="$(ls -1 /usr/local/cuda-*/bin/nvcc 2>/dev/null | sort -V | tail -n1 || true)"
  fi
fi

if [ -n "${_nvcc_path}" ] && [ -x "${_nvcc_path}" ]; then
  NVCC_VERSION="$("${_nvcc_path}" --version 2>/dev/null | sed -n 's/.*release[[:space:]]*\([0-9][0-9.]*\).*/\1/p' | head -n 1 | tr -d '[:space:]')"
  [ -n "${NVCC_VERSION}" ] || NVCC_VERSION="unknown"
fi

#------------------------------------------------------------------------------
# Containers
#------------------------------------------------------------------------------
PODMAN_VERSION="not-detected"
DOCKER_VERSION="not-detected"
if have podman; then PODMAN_VERSION="$(podman --version 2>/dev/null | awk '{print $3}' | tr -d '[:space:]' || echo unknown)"; fi
if have docker; then DOCKER_VERSION="$(docker --version 2>/dev/null | awk '{print $3}' | tr -d ',[:space:]' || echo unknown)"; fi

#------------------------------------------------------------------------------
# Python / ML
#------------------------------------------------------------------------------
PYTHON_VERSION="not-detected"
if have python3; then
  PYTHON_VERSION="$(python3 --version 2>/dev/null | awk '{print $2}' | tr -d '[:space:]' || echo unknown)"
fi

# Prefer Chloe torch venv for torch detection (falls back to system python3)
PREFERRED_TORCH_PY="${ROOT}/.venv/torch/bin/python"
TORCH_PY=""
if [ -x "${PREFERRED_TORCH_PY}" ]; then
  TORCH_PY="${PREFERRED_TORCH_PY}"
elif have python3; then
  TORCH_PY="$(command -v python3)"
fi

TORCH_VER="not-detected"
TORCH_CUDA="not-detected"
TORCH_CUDA_AVAIL="not-detected"

if [ -n "${TORCH_PY}" ] && [ -x "${TORCH_PY}" ]; then
  read -r TORCH_VER TORCH_CUDA TORCH_CUDA_AVAIL < <("${TORCH_PY}" - <<'PY' 2>/dev/null || true
import importlib
torch_ver="not-detected"; torch_cuda="not-detected"; cuda_avail="not-detected"
try:
    torch = importlib.import_module("torch")
    torch_ver = getattr(torch, "__version__", "?")
    torch_cuda = getattr(getattr(torch, "version", None), "cuda", "?")
    try:
        cuda_avail = "true" if bool(torch.cuda.is_available()) else "false"
    except Exception:
        cuda_avail = "not-detected"
except Exception:
    pass
print(torch_ver, torch_cuda, cuda_avail)
PY
  )
fi

#------------------------------------------------------------------------------
# Write STATE/ENVIRONMENT.md
#------------------------------------------------------------------------------
ENV_MD="${STATE_DIR}/ENVIRONMENT.md"
{
  echo "# Environment Snapshot"
  echo "Last verified: ${NOW_UTC}"
  echo
  echo "## OS / Kernel"
  echo "- PRETTY_NAME: ${OS_PRETTY}"
  echo "- VERSION_ID: ${VERSION_ID}"
  echo "- Kernel (uname -a): ${KERNEL_UNAME}"
  echo
  echo "## GPU / Driver / CUDA"
  echo "- GPU: ${GPU_MODEL}"
  echo "- VRAM (reported by nvidia-smi): ${GPU_VRAM_MI} MiB"
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
  if have nvidia-smi; then
    GPU_MEM_USED_MI="$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | head -n1 | sed 's/[[:space:]]*$//' || echo unknown)"
    echo "- GPU memory in use at capture time (rough): ${GPU_MEM_USED_MI} MiB. Close heavy GUI apps before big runs."
  fi
  echo "- This file is GENERATED. Edit SCRIPTS/update_state.sh if you want to change content."
} > "${ENV_MD}"

#------------------------------------------------------------------------------
# Write STATE/INVENTORY.yaml
#------------------------------------------------------------------------------
INV_YAML="${STATE_DIR}/INVENTORY.yaml"
{
  echo "timestamp: \"${NOW_UTC}\""
  echo "hosts:"
  echo "  - name: \"${HOSTNAME_SHORT}\""
  echo "    os: \"${OS_PRETTY}\""
  echo "    version: \"${VERSION_ID}\""
  echo "    kernel: \"${KERNEL_UNAME}\""
  echo "gpus:"
  echo "  - model: \"${GPU_MODEL}\""
  if [[ "${GPU_VRAM_MI}" =~ ^[0-9]+$ ]]; then
    # 8192 MiB -> 8 GiB-ish; keep it simple
    echo "    vram_gb: $(( (GPU_VRAM_MI + 512) / 1024 ))"
  else
    echo "    vram_gb: 0"
  fi
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
} > "${INV_YAML}"

#------------------------------------------------------------------------------
# Write SOP
#------------------------------------------------------------------------------
SOP_MD="${STATE_DIR}/SOP_UPDATE_STATE.md"
{
  echo "# SOP: Update Chloe State"
  echo
  echo "Run:"
  echo
  echo '```bash'
  echo 'cd ~/chloe || exit 1'
  echo 'SCRIPTS/update_state.sh'
  echo '```'
  echo
  echo "Outputs:"
  echo "- STATE/ENVIRONMENT.md"
  echo "- STATE/INVENTORY.yaml"
  echo "- STATE/SOP_UPDATE_STATE.md"
  echo "- Appends to STATE/MAILBOX.md"
} > "${SOP_MD}"

#------------------------------------------------------------------------------
# Append mailbox note (curated, small)
#------------------------------------------------------------------------------
MAILBOX="${STATE_DIR}/MAILBOX.md"
touch "${MAILBOX}"
{
  echo "- ${NOW_UTC} [state]: update_state.sh wrote ENVIRONMENT.md + INVENTORY.yaml"
} >> "${MAILBOX}"

echo "OK: wrote:"
echo "  - ${ENV_MD}"
echo "  - ${INV_YAML}"
echo "  - ${SOP_MD}"
echo "OK: appended mailbox:"
echo "  - ${MAILBOX}"
