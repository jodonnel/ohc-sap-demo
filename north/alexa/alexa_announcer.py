#!/usr/bin/env python3
"""
Alexa Webhook Announcer — Option B (Quick Win)
Watches the demo event count and fires Alexa announcements at milestones.

Uses the free "Webhook Routine Trigger" Alexa skill:
  https://www.amazon.com/dp/B09RGPYHLL

Setup:
  1. Install "Webhook Routine Trigger" skill on your Alexa
  2. Alexa discovers "Trigger1" as a doorbell device
  3. Go to https://trigger.esp8266-server.de/ and log in with your Amazon account
  4. You'll see Trigger1 and its webhook URL
  5. Create more triggers (Trigger2, Trigger3...) — name them:
     - "Demo 100" / "Demo 500" / "Demo 1000" / "Demo Alert"
  6. In Alexa app → Routines:
     - When: Smart Home → "Demo 100" (doorbell press)
     - Action: Alexa Says → Custom → "100 nerve impulses received. The nervous system is waking up."
     - Repeat for each milestone
  7. Copy each trigger's webhook URL into the .env below

Requires: pip install requests
"""

import os
import sys
import time
import json
from pathlib import Path

try:
    import requests
except ImportError:
    print("pip install requests --break-system-packages")
    sys.exit(1)

# ═══ CONFIG ═══
def load_env():
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

load_env()

STATE_URL = os.environ.get("STATE_URL", "https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com/state")
POLL_INTERVAL = int(os.environ.get("ANNOUNCE_POLL", "5"))

# Milestone triggers — map count thresholds to webhook URLs
# Get these URLs from https://trigger.esp8266-server.de/ after setting up the skill
MILESTONES = {}
for key, val in os.environ.items():
    if key.startswith("MILESTONE_"):
        # e.g., MILESTONE_100=https://trigger.esp8266-server.de/api/v1/send/xxxxx
        try:
            count = int(key.split("_", 1)[1])
            MILESTONES[count] = val
        except ValueError:
            pass

if not MILESTONES:
    # Defaults if none configured — these won't fire without real URLs
    print("⚠ No MILESTONE_* URLs found in .env. Configure them first.")
    print("  Example: MILESTONE_100=https://trigger.esp8266-server.de/api/v1/send/YOUR_TOKEN")
    sys.exit(1)


def get_count():
    try:
        resp = requests.get(STATE_URL, timeout=5)
        data = resp.json()
        return data.get("count", 0)
    except Exception as e:
        print(f"  ✗ Failed to get count: {e}")
        return None


def fire_trigger(count, url):
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            print(f"  🔔 FIRED milestone {count}! Alexa should announce now.")
        else:
            print(f"  ✗ Milestone {count} trigger returned HTTP {resp.status_code}")
    except Exception as e:
        print(f"  ✗ Milestone {count} trigger failed: {e}")


def main():
    print("Alexa Webhook Announcer")
    print(f"  State URL: {STATE_URL}")
    print(f"  Poll:      every {POLL_INTERVAL}s")
    print(f"  Milestones: {sorted(MILESTONES.keys())}")
    print(f"  Ctrl+C to stop\n")

    fired = set()
    last_count = 0

    while True:
        try:
            count = get_count()
            if count is None:
                time.sleep(POLL_INTERVAL)
                continue

            if count != last_count:
                print(f"[{time.strftime('%H:%M:%S')}] Count: {count}")
                last_count = count

            # Check milestones
            for threshold in sorted(MILESTONES.keys()):
                if count >= threshold and threshold not in fired:
                    fire_trigger(threshold, MILESTONES[threshold])
                    fired.add(threshold)

            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print("\nStopped.")
            break


if __name__ == "__main__":
    main()
