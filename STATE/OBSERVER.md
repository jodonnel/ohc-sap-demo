# Chloe Observer User (design-in-progress)

User: chloeobserver

Intent:
- Read-mostly system observer for Chloe
- No interactive shell
- SSH access to be gated via ForceCommand entrypoint
- Allowed writes limited to ~/chloe/STATE and ~/chloe/LOGS
- Read access to system logs via systemd-journal group

Current status:
- User exists
- Home directory initialized
- systemd-journal group membership granted
- SSH enforcement NOT YET CONFIGURED

Next step:
- Install sshd_config.d drop-in
- Add chloeobserver-entrypoint script
