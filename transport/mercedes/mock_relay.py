#!/usr/bin/env python3
"""
Mock Mercedes Vehicle → OHC Demo Relay
Generates fake vehicle events for demo purposes

Usage:
  python mock_relay.py          # Send one batch of events
  python mock_relay.py --loop   # Keep sending events every 30s
"""

import sys, json, time, uuid, random, argparse
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    print("pip install requests --break-system-packages")
    sys.exit(1)

NORTH_URL = "https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com"
VEHICLE_ID = "W1NK...2482"  # Redacted VIN

def emit(event_type, data):
    """Emit CloudEvent to OHC demo"""
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    event = {
        "specversion": "1.0",
        "type": f"ohc.demo.vehicle.{event_type}",
        "source": "mercedes://mock-relay",
        "id": f"mb-mock-{uuid.uuid4().hex[:8]}",
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
    return r.status_code == 200 if 'r' in locals() else False

def send_vehicle_events():
    """Send a batch of realistic vehicle events"""

    # Fuel level (gradually decreasing)
    fuel_pct = random.randint(65, 85)
    range_km = int(fuel_pct * 7.5)  # ~500km range at full tank
    emit("fuel", {
        "vehicle": VEHICLE_ID,
        "fuel_pct": fuel_pct,
        "range_km": range_km,
        "description": f"Fuel: {fuel_pct}% ({range_km} km range)"
    })

    # Odometer (slowly increasing)
    odometer = random.randint(45000, 45100)
    emit("odometer", {
        "vehicle": VEHICLE_ID,
        "odometer_km": odometer,
        "description": f"Odometer: {odometer:,} km"
    })

    # Lock status (usually locked)
    locked = random.choice([True, True, True, False])  # 75% locked
    emit("lock_status", {
        "vehicle": VEHICLE_ID,
        "locked": locked,
        "description": f"Vehicle {'locked' if locked else 'UNLOCKED'}"
    })

    # Tire pressure
    tire_kpa = random.randint(220, 250)
    emit("tire_pressure", {
        "vehicle": VEHICLE_ID,
        "front_left_kpa": tire_kpa,
        "description": f"Tire FL: {tire_kpa} kPa"
    })

    # Location ping (coords redacted, just confirmation)
    emit("location_ping", {
        "vehicle": VEHICLE_ID,
        "has_fix": True,
        "description": "Location updated (coords redacted)"
    })

    # Battery voltage (healthy range)
    battery_v = round(random.uniform(12.4, 14.2), 1)
    emit("battery", {
        "vehicle": VEHICLE_ID,
        "voltage": battery_v,
        "status": "healthy" if battery_v > 12.6 else "check",
        "description": f"Battery: {battery_v}V"
    })

def main():
    p = argparse.ArgumentParser(description="Mock Mercedes → OHC Relay")
    p.add_argument("--loop", action="store_true", help="Keep sending events every 30s")
    args = p.parse_args()

    print(f"\n{'='*60}")
    print(f" MOCK MERCEDES → OHC RELAY")
    print(f"{'='*60}")
    print(f" Vehicle:   {VEHICLE_ID} (mock data)")
    print(f" Target:    {NORTH_URL}/ingest")
    print(f" Mode:      {'CONTINUOUS' if args.loop else 'ONE-SHOT'}")
    print(f"{'='*60}\n")

    if args.loop:
        print("Press Ctrl+C to stop\n")
        cycle = 0
        try:
            while True:
                cycle += 1
                print(f"── Cycle #{cycle} ──")
                send_vehicle_events()
                print()
                time.sleep(30)
        except KeyboardInterrupt:
            print("\n\nMock relay stopped. 🚗")
    else:
        send_vehicle_events()
        print(f"\n✓ Mock vehicle events sent to demo")
        print(f"   View at: {NORTH_URL}/dashboard\n")

if __name__ == "__main__":
    main()
