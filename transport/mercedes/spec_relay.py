#!/usr/bin/env python3
"""
Mercedes Vehicle Specification → OHC Demo Relay
Uses Vehicle Specification API (API Key auth) instead of OAuth2
Queries vehicle specs by VIN and emits as CloudEvents

Usage:
  1. Copy .env.spec.example → .env.spec
  2. Add MB_API_KEY and MB_VIN
  3. python spec_relay.py
"""

import os, sys, json, time, uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
    from dotenv import load_dotenv
except ImportError:
    print("pip install requests python-dotenv --break-system-packages")
    sys.exit(1)

load_dotenv(".env.spec")

API_KEY = os.getenv("MB_API_KEY", "")
VIN = os.getenv("MB_VIN", "")
NORTH_URL = os.getenv("NORTH_URL", "https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com")

# Vehicle Specification API endpoint
SPEC_API_BASE = "https://api.mercedes-benz.com/vehicle-specification/v1"

def api_get(endpoint):
    """Call Vehicle Specification API with API Key"""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "application/json"
    }
    try:
        url = f"{SPEC_API_BASE}{endpoint}"
        print(f"  → GET {url}")
        r = requests.get(url, headers=headers, timeout=15)
        print(f"  ← {r.status_code}")
        if r.status_code == 200:
            return r.json()
        else:
            print(f"  Error: {r.text}")
            return None
    except Exception as e:
        print(f"  API error: {e}")
        return None

def emit(event_type, data):
    """Emit CloudEvent to OHC demo"""
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    event = {
        "specversion": "1.0",
        "type": f"ohc.demo.vehicle.{event_type}",
        "source": "mercedes://spec-relay",
        "id": f"mb-spec-{uuid.uuid4().hex[:8]}",
        "time": now,
        "eventclass": "vehicle",
        "data": data,
    }
    try:
        r = requests.post(f"{NORTH_URL}/ingest", json=event, timeout=10)
        sym = "✓" if r.status_code == 200 else f"✗ {r.status_code}"
    except Exception as e:
        sym = f"✗ {e}"

    ts = datetime.now().strftime("%H:%M:%S")
    print(f"  [{ts}] {event_type:.<30s} {sym}")

def get_vehicle_spec(vin):
    """Get vehicle specifications by VIN"""
    # Try different endpoints
    endpoints = [
        f"/vehicles/{vin}",
        f"/vehicles/{vin}/specification",
        f"/specifications/{vin}"
    ]

    for endpoint in endpoints:
        spec = api_get(endpoint)
        if spec:
            return spec

    return None

def run():
    if not API_KEY:
        print("ERROR: Set MB_API_KEY in .env.spec")
        sys.exit(1)

    if not VIN:
        print("ERROR: Set MB_VIN (your vehicle VIN) in .env.spec")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f" MERCEDES VEHICLE SPEC → OHC RELAY")
    print(f"{'='*60}")
    print(f" VIN:       {VIN[:8]}...{VIN[-4:]}")
    print(f" Target:    {NORTH_URL}/ingest")
    print(f" API:       Vehicle Specification (API Key)")
    print(f"{'='*60}\n")

    # Get vehicle spec
    print("Fetching vehicle specification...")
    spec = get_vehicle_spec(VIN)

    if not spec:
        print("\n❌ Could not retrieve vehicle specification")
        print("   Check your VIN and API key")
        sys.exit(1)

    print(f"\n✓ Got vehicle specification:")
    print(json.dumps(spec, indent=2))

    # Emit spec as event
    emit("specification", {
        "vin": VIN[:8] + "..." + VIN[-4:],
        "spec": spec,
        "description": f"Vehicle specification for {VIN[:8]}..."
    })

    print(f"\n✓ Vehicle spec relayed to demo")
    print(f"\nNote: Vehicle Specification API provides static data, not live telemetry.")
    print(f"For live data (fuel, location, locks), you need Vehicle Status 1.5 Business (pending approval).\n")

if __name__ == "__main__":
    run()
