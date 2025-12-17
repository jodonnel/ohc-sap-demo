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
