# Chloe Mailbox

## How to write
Add this helper to your shell:

  chloe_mail () { echo "- $(date -u +'%Y-%m-%dT%H:%M:%SZ') [${1:-note}]: ${2:-(no message)}" >> $HOME/chloe/STATE/MAILBOX.md; tail -n 5 $HOME/chloe/STATE/MAILBOX.md; }

## Recent
- 2025-12-15T18:42:20Z [init]: Mailbox created from /home/jodonnell/chloe/DIAG/reports/selective_2025-12-15T18:39:06Z.txt
- 2025-12-15T20:53:17Z [state]: update_state.sh wrote ENVIRONMENT.md + INVENTORY.yaml (report: ~/chloe/DIAG/crash/crash_2025-12-15T20:52:54Z.txt)
