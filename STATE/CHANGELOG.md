- 2025-12-15T18:42:20Z: Initialized ENVIRONMENT.md & INVENTORY.yaml from /home/jodonnell/chloe/DIAG/reports/selective_2025-12-15T18:39:06Z.txt.

- 2025-12-17T08:04:04Z [obs/meet/firefox]: RHEL 10 Wayland+PipeWire: Firefox may not enumerate OBS v4l2loopback virtual camera in Google Meet. Fix: about:config media.webrtc.camera.allow-pipewire=false; restart Firefox; re-allow camera permission for meet.google.com. Verify /dev/video10 name and OBS holds it via fuser.
