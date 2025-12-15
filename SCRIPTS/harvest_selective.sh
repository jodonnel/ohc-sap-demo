#!/usr/bin/env bash
set -euo pipefail

START_DIR="${1:-$HOME}"              # default: your home
MAXDEPTH="${MAXDEPTH:-10}"           # how deep to search
LINES="${LINES:-160}"                # how many lines to cat per file
DAYS="${DAYS:-365}"                  # mtime window for "recent" lists

TS="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
OUTDIR="$HOME/chloe/DIAG/reports"
OUT="$OUTDIR/selective_${TS}.txt"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$OUTDIR"

sec(){ printf "\n===== %s =====\n" "$1"; }
print_file(){
  local f="$1"
  [ -f "$f" ] || return 0
  local sz="$(stat -c %s "$f" 2>/dev/null || echo 0)"
  echo "### FILE: $f  (size: ${sz} bytes)"
  sed -n "1,${LINES}p" "$f" 2>/dev/null || true
  local total_lines="$(wc -l < "$f" 2>/dev/null || echo 0)"
  if [ "$total_lines" -gt "$LINES" ]; then
    echo "--- [truncated: showing first ${LINES}/${total_lines} lines] ---"
  fi
}

{
  sec "HARVEST_META"
  echo "timestamp: $TS"
  echo "start_dir: $START_DIR"
  echo "maxdepth: $MAXDEPTH, preview_lines: $LINES, recent_days: $DAYS"

  sec "OS_KERNEL"
  uname -a || true
  [ -f /etc/os-release ] && cat /etc/os-release || true
  cat /proc/version 2>/dev/null || true
  wsl.exe --status 2>/dev/null || true

  sec "GPU_CUDA"
  nvidia-smi || true
  nvcc --version 2>/dev/null || true
  cat /proc/driver/nvidia/version 2>/dev/null || true

  sec "PYTHON_TOOLING"
  python3 --version 2>/dev/null || true
  python3 - <<'PY' 2>/dev/null || true
import importlib, sys
mods = ['torch','transformers','vllm','numpy','accelerate','bitsandbytes']
for m in mods:
    try:
        mod=importlib.import_module(m)
        print(m, getattr(mod,'__version__','?'))
    except Exception:
        print(m, 'not-found')
try:
    import torch
    print('torch_cuda', getattr(torch.version,'cuda','?'), 'cuda_available', torch.cuda.is_available())
except Exception:
    pass
PY

  sec "CONTAINERS"
  podman --version 2>/dev/null || true
  docker --version 2>/dev/null || true

  # 1) Likely Chloe state & handoff/mailbox/status files by NAME
  sec "STATE_FILE_CANDIDATES (by name)"
  find "$START_DIR" -maxdepth "$MAXDEPTH" -type f \
    -regextype posix-extended \
    -iregex '.*(ENVIRONMENT\.md|INVENTORY\.ya?ml|CHANGELOG\.md|RISKLOG\.md|TODO\.md|SYSTEM\.md|SOP_.*\.md|STATUS(\.md|\.txt|\.log)?|H(AND)?(O|\-)?(FF|VER).*(\.md|\.txt|\.log)?|MAILBOX\.md|INBOX\.md|OUTBOX\.md|HEARTBEAT(\.log)?|SYNC(LOG)?|STATE(\.md)?).*' \
    2>/dev/null | sort -u | tee "$TMP/by_name.txt"
  while read -r f; do [ -n "$f" ] && print_file "$f"; done < "$TMP/by_name.txt"

  # 2) Likely Chloe files by CONTENT phrases
  sec "STATE_FILE_CANDIDATES (by content)"
  if command -v rg >/dev/null 2>&1; then
    rg -n --pcre2 --max-filesize 2M --ignore-case --no-heading \
      -e '(handoff|hand\-off|handover|last verified|updated at|timestamp:|status board|dear future me|note to self|chloe mailbox|chloe heartbeat)' \
      "$START_DIR" 2>/dev/null | tee "$TMP/by_content.txt"
  else
    grep -RIn --binary-files=without-match --max-filesize=2097152 \
      -e 'handoff\|hand-off\|handover\|last verified\|updated at\|timestamp:\|status board\|dear future me\|note to self\|chloe mailbox\|chloe heartbeat' \
      "$START_DIR" 2>/dev/null | tee "$TMP/by_content.txt"
  fi

  # 3) Recently touched likely files
  sec "RECENT_STATE_FILES (last ${DAYS} days)"
  find "$START_DIR" -type f -mtime "-$DAYS" -maxdepth "$MAXDEPTH" \
    -regextype posix-extended \
    -iregex '.*(ENVIRONMENT\.md|INVENTORY\.ya?ml|CHANGELOG\.md|RISKLOG\.md|TODO\.md|SYSTEM\.md|SOP_.*\.md|STATUS.*|HANDOFF.*|MAILBOX.*|HEARTBEAT.*|SYNC.*|STATE.*)' \
    -printf "%T@ %TY-%Tm-%Td %TT %p\n" 2>/dev/null | sort -nr | head -n 60 | tee "$TMP/recent.txt"
  cut -d' ' -f4- "$TMP/recent.txt" | while read -r f; do [ -n "$f" ] && print_file "$f"; done

  # 4) Git repos: list a few and show short context
  sec "GIT_REPOS"
  mapfile -t REPOS < <(find "$START_DIR" -maxdepth "$MAXDEPTH" -type d -name ".git" 2>/dev/null | sed 's|/.git$||' | sort -u)
  echo "FOUND_REPOS: ${#REPOS[@]}"
  for r in "${REPOS[@]}"; do
    echo "--- REPO: $r ---"
    git -C "$r" rev-parse --abbrev-ref HEAD 2>/dev/null || true
    git -C "$r" remote -v 2>/dev/null | sed 's/^/  /' || true
    git -C "$r" --no-pager log --oneline -n 5 2>/dev/null | sed 's/^/  /' || true
    echo "  tracked-hints:"
    git -C "$r" ls-files 2>/dev/null | grep -Ei '(ENVIRONMENT\.md|INVENTORY\.ya?ml|CHANGELOG\.md|RISKLOG\.md|TODO\.md|SOP_|SYSTEM\.md|instructlab|taxonomy|ansible|kustomization\.ya?ml|docker-compose\.ya?ml|compose\.ya?ml|Containerfile|Dockerfile|Taskfile\.ya?ml|vllm|llama|models\.(json|ya?ml))' || true
  done

  # 5) Model artifacts (top by size)
  sec "MODEL_ARTIFACTS (top 30 by size)"
  find "$START_DIR" -maxdepth "$MAXDEPTH" -type f \
    \( -iname "*.gguf" -o -iname "*.safetensors" -o -iname "*.onnx" \) \
    -printf "%p\t%k KB\n" 2>/dev/null | sort -k2nr | head -n 30

} > "$OUT"

echo "HARVEST_WROTE: $OUT"
