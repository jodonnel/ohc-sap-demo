#!/usr/bin/env bash
set -euo pipefail

export ASK="${ASK:-Given this setup (RHEL 10.1, CUDA 13.x, Qwen2.5-3B :8001, Mistral-7B Q2_K :8002), propose ONE next step to improve reliability & ergonomics. ≤5 lines. Include exact commands.}"

# Ask a llama.cpp server with a tiny Python JSON builder; prints .content or nothing.
ask_model() {
  local port="$1" template="$2"
  local payload
  payload="$(
python3 - <<'PY'
import json,os,sys
ask=os.environ.get("ASK","")
tpl=os.environ.get("TEMPLATE","qwen")
if tpl=="qwen":
    prompt=f"<|im_start|>system\nYou are Chloe, Jim’s local assistant. Be concise.\n<|im_end|>\n<|im_start|>user\n{ask}\n<|im_end|>\n<|im_start|>assistant\n"
else:
    prompt=f"[INST] System: You are Chloe, Jim’s local assistant. Be concise. [/INST][INST] {ask} [/INST]"
print(json.dumps({"prompt":prompt,"n_predict":192}))
PY
  )"
  curl --max-time 20 -s "http://127.0.0.1:${port}/completion" \
    -H 'Content-Type: application/json' --data-binary "$payload" \
  | python3 - <<'PY' 2>/dev/null || true
import sys,json
try: print(json.load(sys.stdin).get("content","").strip())
except Exception: pass
PY
}

TEMPLATE=qwen    QWEN_ANS="$(ask_model 8001 qwen || true)"
TEMPLATE=mistral MISTRAL_ANS="$(ask_model 8002 mistral || true)"

# Keep "Chloe" to <=5 lines + exact commands
read -r -d '' CHLOE_ANS <<'TXT'
Use user-level systemd to auto-restart both servers on failure.
Commands:
mkdir -p ~/.config/systemd/user && systemctl --user daemon-reload
printf '%s\n' '[Unit]\n[Service]\nExecStart=%h/src/llama.cpp/build/bin/llama-server -m %h/models/Qwen2.5-3B-Instruct-Q4_K_M.gguf --port 8001 --ctx-size 4096 --n-gpu-layers 999\nRestart=always\n[Install]\nWantedBy=default.target' > ~/.config/systemd/user/llama-qwen.service
printf '%s\n' '[Unit]\n[Service]\nExecStart=%h/src/llama.cpp/build/bin/llama-server -m %h/models/mistral-7b-instruct-v0.2.Q2_K.gguf --port 8002 --ctx-size 2048 --n-gpu-layers 999\nRestart=always\n[Install]\nWantedBy=default.target' > ~/.config/systemd/user/llama-mistral.service
systemctl --user enable --now llama-qwen.service llama-mistral.service
TXT

# Print, score, and pick a winner.
python3 - <<'PY'
import os,re
ask=os.environ["ASK"]
qa={"Qwen":os.environ.get("QWEN_ANS",""),
    "Mistral":os.environ.get("MISTRAL_ANS",""),
    "Chloe":os.environ.get("CHLOE_ANS","")}
def score(ans:str)->int:
    s=0
    lines=[l for l in ans.strip().splitlines() if l.strip()]
    if 1<=len(lines)<=5: s+=2
    if re.search(r'\b(curl|llama-(server|cli)|systemctl|--port|--ctx-size)\b', ans): s+=3
    if any(x in ans for x in ("Qwen2.5-3B","mistral-7b","llama-server",".config/systemd/user")): s+=3
    if any(b in ans.lower() for b in ("can't","cannot","sorry","as an ai")): s-=3
    return s
print("==== QUESTION ====\n"+ask+"\n")
for k,v in qa.items():
    print(f"---- {k} ----\n{(v.strip() or '<no answer>')}\n")
print("==== SCORES ====")
scores={k:score(v) for k,v in qa.items()}
for k,v in scores.items(): print(f"{k}:{v}")
best=max(scores, key=lambda k:(scores[k], k=="Qwen"))
print("\nWINNER:", best)
PY
