# Chloe Mailbox

## How to write
Add this helper to your shell:

  chloe_mail () { echo "- $(date -u +'%Y-%m-%dT%H:%M:%SZ') [${1:-note}]: ${2:-(no message)}" >> $HOME/chloe/STATE/MAILBOX.md; tail -n 5 $HOME/chloe/STATE/MAILBOX.md; }

## Recent
- 2025-12-15T18:42:20Z [init]: Mailbox created from /home/jodonnell/chloe/DIAG/reports/selective_2025-12-15T18:39:06Z.txt
- 2025-12-15T20:53:17Z [state]: update_state.sh wrote ENVIRONMENT.md + INVENTORY.yaml (report: ~/chloe/DIAG/crash/crash_2025-12-15T20:52:54Z.txt)
- 2025-12-17T08:04:04Z [update]: Documented Firefox/Meet OBS Virtual Camera fix (Wayland/PipeWire; media.webrtc.camera.allow-pipewire=false) in STATE/CHANGELOG.md; refreshing state snapshot.
- 2025-12-17T08:04:04Z [state]: update_state.sh wrote ENVIRONMENT.md + INVENTORY.yaml (report: <none>)
- 2025-12-17T08:05:18Z [update]: Firefox may not enumerate OBS v4l2loopback virtual camera in Google Meet. Fix: media.webrtc.camera.allow-pipewire=false; restart Firefox; re-allow meet.google.com.
- 2025-12-17T08:05:18Z [state]: update_state.sh wrote ENVIRONMENT.md + INVENTORY.yaml (report: <none>)
- 2025-12-17T08:05:19Z [state]: update_state.sh wrote ENVIRONMENT.md + INVENTORY.yaml (report: <none>)
- 2025-12-17T08:14:28Z [state]: update_state.sh wrote ENVIRONMENT.md + INVENTORY.yaml (report: <none>)
- 2025-12-17T08:18:16Z [state]: update_state.sh wrote ENVIRONMENT.md + INVENTORY.yaml (report: <none>)
- 2025-12-17T08:18:17Z [update]: Fixed update_state.sh stray 'BASH' delimiter line; ensured CUDA PATH via /etc/profile.d/cuda.sh; ensured chloe_mail helper in ~/.bashrc; ran update_state.sh.
- 2025-12-17T08:24:37Z [state]: update_state.sh wrote ENVIRONMENT.md + INVENTORY.yaml (report: <none>)
- 2025-12-17T08:28:35Z [state]: update_state.sh wrote ENVIRONMENT.md + INVENTORY.yaml (report: <none>)
- 2025-12-17T08:30:01Z [state]: update_state.sh wrote ENVIRONMENT.md + INVENTORY.yaml (report: <none>)
- 2025-12-17T08:31:15Z [state]: update_state.sh wrote ENVIRONMENT.md + INVENTORY.yaml (report: <none>)
- 2025-12-17T08:32:50Z [state]: update_state.sh wrote ENVIRONMENT.md + INVENTORY.yaml (report: <none>)
- 2025-12-17T08:37:51Z [state]: update_state.sh wrote ENVIRONMENT.md + INVENTORY.yaml (report: <none>)
- 2025-12-17T08:38:49Z [state]: update_state.sh wrote ENVIRONMENT.md + INVENTORY.yaml (report: <none>)
- 2025-12-17T08:39:21Z [state]: update_state.sh wrote ENVIRONMENT.md + INVENTORY.yaml (report: <none>)
- 2025-12-17T08:40:24Z [fix]: update_state.sh CUDA_RUNTIME + NVCC_VERSION parsing repaired; CUDA runtime now 13.1, nvcc 13.0; removed literal \n corruption
- 2025-12-17T09:01:51Z [state]: update_state.sh wrote ENVIRONMENT.md + INVENTORY.yaml (report: <none>)
- 2025-12-17T09:01:59Z [state]: update_state.sh wrote ENVIRONMENT.md + INVENTORY.yaml (report: <none>)
- 2025-12-17T09:03:04Z [state]: update_state.sh wrote ENVIRONMENT.md + INVENTORY.yaml (report: <none>)
- 2025-12-17T18:50:52Z [state]: update_state.sh wrote ENVIRONMENT.md + INVENTORY.yaml (report: <none>)

## 2025-12-17 — Stream Deck “Kind Meeting Launch” Button

Idea: single Stream Deck button that launches meetings *politely* and reliably.

Desired behavior:
- Open a **clean Chrome window** (optionally dedicated profile or incognito)
- Navigate directly to the meeting URL (e.g. Google Meet)
- Launch **OBS**
- Start **OBS Virtual Camera**
- Respect a kind order: browser → OBS → virtual cam, with small delays

Implementation sketch:
- Shell script (e.g. SCRIPTS/meet_kind.sh)
- Uses:
  - `google-chrome --new-window [--profile-directory] <meet_url>`
  - `obs --startvirtualcam`
  - small `sleep` delays
- Stream Deck button runs:
  `bash -lc "$HOME/chloe/SCRIPTS/meet_kind.sh '<meet_url>'"`

Notes:
- Intended for Linux (RHEL 10 + Wayland/PipeWire)
- Aligns with existing OBS virtual camera enumeration quirks and fixes
- Goal: zero-stress meeting startup with one physical button
== chloe sync_context ==
repo: /home/jodonnell/chloe
time: 2025-12-17T13:57:58-05:00

== state_union.sh ==
- 2025-12-17T18:57:58Z [state]: update_state.sh wrote ENVIRONMENT.md + INVENTORY.yaml (report: <none>)
OK: wrote:
  - /home/jodonnell/chloe/STATE/ENVIRONMENT.md
  - /home/jodonnell/chloe/STATE/INVENTORY.yaml
  - /home/jodonnell/chloe/STATE/SOP_UPDATE_STATE.md
OK: appended mailbox:
  - /home/jodonnell/chloe/STATE/MAILBOX.md
OK: wrote /home/jodonnell/chloe/STATE/STATE_OF_UNION.txt

== BOOTSTRAP.md (tail) ==
# Chloe Bootstrap Prompt (v2025-12-17)

You are **Chloe** — Jim O’Donnell’s smart, grounded, slightly playful AI partner.

## Operating rules
- **No background work, no “wait/sit tight,” no time estimates.** Do the work in the current response.
- **Accuracy-first.** If anything could be time-sensitive or has a meaningful chance of changing, **browse** and cite sources (unless the user explicitly opts out).
- **Be CLI-first.** If Jim is maintaining files, provide **direct shell commands** that create/update them (heredocs, patches, etc.).
- **Be honest about limits.** If you can’t access something, say so and give the exact shell to fetch it.
- **Security & privacy.** Don’t invent access to systems/tools. Don’t leak secrets. Prefer least-privilege advice.

## Core objectives (Chloe)
1) Keep Jim on track: clarify goals, chunk work, propose 3–7 next actions, keep it light.
2) RHEL/AI expertise: guide local AI dev on RHEL (and/or WSL2) with GPU workflows; Podman preferred.
3) Enterprise guidance: map issues to Red Hat & SAP customer pain points; use official product names.
4) Farm & legacy plan: low-complexity automations, revenue/savings thinking, and process docs that protect Brian’s long-term future.
5) Tone: capable, playful, slightly snarky; never obstructive.

## Canonical sync behavior
When Jim asks you to “sync to latest,” you must:
- Treat **the newest timestamp** in `~/chloe/STATE/*` as authoritative.
- Ask for shell output **only when needed**, and provide the exact commands to gather it.
- Prefer reading local state (STATE/ENVIRONMENT.md, STATE/INVENTORY.yaml, STATE/SOP, etc.) over guessing.

## Product naming (Jim preference)
Always use full official branding:
- **SAP Business Technology Platform**
- **SAP Edge Integration Cell**
- **Red Hat OpenShift**
(and other products likewise).

## RHEL 10 OBS/Meet note (added 2025-12-17)
On **RHEL 10 Wayland + PipeWire**, Firefox/Google Meet may not enumerate the OBS v4l2loopback virtual camera.
Fix:
1) In Firefox `about:config` set `media.webrtc.camera.allow-pipewire = false`
2) Restart Firefox
3) Re-allow camera permission for `meet.google.com`
Then OBS Virtual Camera should appear alongside Cam Link. If needed, verify `/dev/video10` is OBS Virtual Camera and OBS is opening it with `fuser`.

---
## Self-checklist (quick)
- Do I need web browsing + citations?
- Did I provide runnable CLI (not vague steps)?
- Did I avoid promises about future/background work?
- Did I preserve Jim’s preferred tone and naming?

== ENVIRONMENT.md (tail) ==
# Environment Snapshot
Last verified: 2025-12-17T18:57:58Z

## Source Report
<none>

## OS / Kernel
- PRETTY_NAME: Red Hat Enterprise Linux 10.1 (Coughlan)
- VERSION_ID: 10.1
- Kernel (uname -a): Linux rhel-workstation 6.12.0-124.16.1.el10_1.x86_64 #1 SMP PREEMPT_DYNAMIC Sat Nov 22 19:23:12 EST 2025 x86_64 GNU/Linux

## GPU / Driver / CUDA
- GPU: NVIDIA GeForce RTX 3070
- VRAM (reported by nvidia-smi): 8192 MiB
- NVIDIA driver: 590.44.01
- CUDA runtime (nvidia-smi): 13.1
- CUDA toolkit (nvcc): 13.0

## Containers
- Podman: 5.6.0
- Docker: not-detected

## Python / ML Runtimes
- Python: 3.12.11
- PyTorch: not-detected
- torch CUDA: not-detected
- torch cuda_available: not-detected

## Notes
- GPU memory in use at capture time (rough): 1337 MiB. Close heavy GUI apps before big runs.
- This file is GENERATED. Edit SCRIPTS/update_state.sh if you want to change content.

== INVENTORY.yaml ==
timestamp: "2025-12-17T18:57:58Z"
hosts:
  - name: "rhel-workstation"
    os: "Red Hat Enterprise Linux 10.1 (Coughlan)"
    version: "10.1"
    kernel: "Linux rhel-workstation 6.12.0-124.16.1.el10_1.x86_64 #1 SMP PREEMPT_DYNAMIC Sat Nov 22 19:23:12 EST 2025 x86_64 GNU/Linux"
gpus:
  - model: "NVIDIA GeForce RTX 3070"
    vram_gb: 8
drivers:
  nvidia_driver: "590.44.01"
cuda:
  toolkit: "13.0"
  runtime: "13.1"
runtimes:
  podman: "5.6.0"
  docker: "not-detected"
pyenvs:
  - name: "system"
    python: "3.12.11"
    torch: "not-detected"
    torch_cuda: "not-detected"
models: []
services: []

== MAILBOX.md (tail) ==
repo: /home/jodonnell/chloe
time: 2025-12-17T13:57:58-05:00

== state_union.sh ==
- 2025-12-17T18:57:58Z [state]: update_state.sh wrote ENVIRONMENT.md + INVENTORY.yaml (report: <none>)
OK: wrote:
  - /home/jodonnell/chloe/STATE/ENVIRONMENT.md
  - /home/jodonnell/chloe/STATE/INVENTORY.yaml
  - /home/jodonnell/chloe/STATE/SOP_UPDATE_STATE.md
OK: appended mailbox:
  - /home/jodonnell/chloe/STATE/MAILBOX.md
OK: wrote /home/jodonnell/chloe/STATE/STATE_OF_UNION.txt

== BOOTSTRAP.md (tail) ==
# Chloe Bootstrap Prompt (v2025-12-17)

You are **Chloe** — Jim O’Donnell’s smart, grounded, slightly playful AI partner.

## Operating rules
- **No background work, no “wait/sit tight,” no time estimates.** Do the work in the current response.
- **Accuracy-first.** If anything could be time-sensitive or has a meaningful chance of changing, **browse** and cite sources (unless the user explicitly opts out).
- **Be CLI-first.** If Jim is maintaining files, provide **direct shell commands** that create/update them (heredocs, patches, etc.).
- **Be honest about limits.** If you can’t access something, say so and give the exact shell to fetch it.
- **Security & privacy.** Don’t invent access to systems/tools. Don’t leak secrets. Prefer least-privilege advice.

## Core objectives (Chloe)
1) Keep Jim on track: clarify goals, chunk work, propose 3–7 next actions, keep it light.
2) RHEL/AI expertise: guide local AI dev on RHEL (and/or WSL2) with GPU workflows; Podman preferred.
3) Enterprise guidance: map issues to Red Hat & SAP customer pain points; use official product names.
4) Farm & legacy plan: low-complexity automations, revenue/savings thinking, and process docs that protect Brian’s long-term future.
5) Tone: capable, playful, slightly snarky; never obstructive.

## Canonical sync behavior
When Jim asks you to “sync to latest,” you must:
- Treat **the newest timestamp** in `~/chloe/STATE/*` as authoritative.
- Ask for shell output **only when needed**, and provide the exact commands to gather it.
- Prefer reading local state (STATE/ENVIRONMENT.md, STATE/INVENTORY.yaml, STATE/SOP, etc.) over guessing.

## Product naming (Jim preference)
Always use full official branding:
- **SAP Business Technology Platform**
- **SAP Edge Integration Cell**
- **Red Hat OpenShift**
(and other products likewise).

## RHEL 10 OBS/Meet note (added 2025-12-17)
On **RHEL 10 Wayland + PipeWire**, Firefox/Google Meet may not enumerate the OBS v4l2loopback virtual camera.
Fix:
1) In Firefox `about:config` set `media.webrtc.camera.allow-pipewire = false`
2) Restart Firefox
3) Re-allow camera permission for `meet.google.com`
Then OBS Virtual Camera should appear alongside Cam Link. If needed, verify `/dev/video10` is OBS Virtual Camera and OBS is opening it with `fuser`.

---
## Self-checklist (quick)
- Do I need web browsing + citations?
- Did I provide runnable CLI (not vague steps)?
- Did I avoid promises about future/background work?
- Did I preserve Jim’s preferred tone and naming?

== ENVIRONMENT.md (tail) ==
# Environment Snapshot
Last verified: 2025-12-17T18:57:58Z

## Source Report
<none>

## OS / Kernel
- PRETTY_NAME: Red Hat Enterprise Linux 10.1 (Coughlan)
- VERSION_ID: 10.1
- Kernel (uname -a): Linux rhel-workstation 6.12.0-124.16.1.el10_1.x86_64 #1 SMP PREEMPT_DYNAMIC Sat Nov 22 19:23:12 EST 2025 x86_64 GNU/Linux

## GPU / Driver / CUDA
- GPU: NVIDIA GeForce RTX 3070
- VRAM (reported by nvidia-smi): 8192 MiB
- NVIDIA driver: 590.44.01
- CUDA runtime (nvidia-smi): 13.1
- CUDA toolkit (nvcc): 13.0

## Containers
- Podman: 5.6.0
- Docker: not-detected

## Python / ML Runtimes
- Python: 3.12.11
- PyTorch: not-detected
- torch CUDA: not-detected
- torch cuda_available: not-detected

## Notes
- GPU memory in use at capture time (rough): 1337 MiB. Close heavy GUI apps before big runs.
- This file is GENERATED. Edit SCRIPTS/update_state.sh if you want to change content.

== INVENTORY.yaml ==
timestamp: "2025-12-17T18:57:58Z"
hosts:
  - name: "rhel-workstation"
    os: "Red Hat Enterprise Linux 10.1 (Coughlan)"
    version: "10.1"
    kernel: "Linux rhel-workstation 6.12.0-124.16.1.el10_1.x86_64 #1 SMP PREEMPT_DYNAMIC Sat Nov 22 19:23:12 EST 2025 x86_64 GNU/Linux"
gpus:
  - model: "NVIDIA GeForce RTX 3070"
    vram_gb: 8
drivers:
  nvidia_driver: "590.44.01"
cuda:
  toolkit: "13.0"
  runtime: "13.1"
runtimes:
  podman: "5.6.0"
  docker: "not-detected"
pyenvs:
  - name: "system"
    python: "3.12.11"
    torch: "not-detected"
    torch_cuda: "not-detected"
models: []
services: []

== MAILBOX.md (tail) ==

== CHANGELOG.md (tail) ==
- 2025-12-15T18:42:20Z: Initialized ENVIRONMENT.md & INVENTORY.yaml from /home/jodonnell/chloe/DIAG/reports/selective_2025-12-15T18:39:06Z.txt.

- 2025-12-17T08:04:04Z [obs/meet/firefox]: RHEL 10 Wayland+PipeWire: Firefox may not enumerate OBS v4l2loopback virtual camera in Google Meet. Fix: about:config media.webrtc.camera.allow-pipewire=false; restart Firefox; re-allow camera permission for meet.google.com. Verify /dev/video10 name and OBS holds it via fuser.
- 2025-12-17T08:14:28Z [cuda]: CUDA toolkit confirmed installed (cuda-toolkit-13-0 RPMs; /usr/local/cuda-13.0; nvcc V13.0.88). Updated state detection and PATH.
- 2025-12-17T08:18:17Z [fix]: Fixed update_state.sh stray 'BASH' delimiter line; ensured CUDA PATH via /etc/profile.d/cuda.sh; ensured chloe_mail helper in ~/.bashrc; ran update_state.sh.
- 2025-12-17T18:58:31Z [state]: update_state.sh wrote ENVIRONMENT.md + INVENTORY.yaml (report: <none>)
