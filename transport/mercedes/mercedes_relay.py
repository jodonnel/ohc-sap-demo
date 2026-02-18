#!/usr/bin/env python3
"""
Mercedes-Benz → OHC Demo Relay
Polls your personal Mercedes via the Connected Vehicle API.
Wraps telemetry as CloudEvents and POSTs to /ingest.

LEGAL: This reads YOUR car with YOUR Mercedes me credentials.
       Read-only. No remote commands. No secrets in repo.

SETUP:
  1. Register at https://developer.mercedes-benz.com/
  2. Log in with your Mercedes me account
  3. Create a Project → add Connected Vehicle APIs (read-only scopes)
  4. Note your Client ID and Client Secret
  5. Copy .env.example → .env and fill in values
  6. pip install requests python-dotenv
  7. python mercedes_relay.py --auth   (first time — opens browser for OAuth)
  8. python mercedes_relay.py           (runs the relay)

READS (all read-only):
  - Fuel level + range
  - Odometer
  - Lock status (doors/trunk)
  - Tire pressure
  - Location (redacted in events — only "has_location: true")

DOES NOT:
  - Lock/unlock
  - Climate control
  - Horn/lights
  - Any write operation
"""

import os, sys, json, time, uuid, argparse, webbrowser
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
    from dotenv import load_dotenv
except ImportError:
    print("pip install requests python-dotenv --break-system-packages")
    sys.exit(1)

load_dotenv()

CLIENT_ID     = os.getenv("MB_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("MB_CLIENT_SECRET", "")
REDIRECT_URI  = os.getenv("MB_REDIRECT_URI", "http://localhost:9090/callback")
VEHICLE_ID    = os.getenv("MB_VEHICLE_ID", "")
NORTH_URL     = os.getenv("NORTH_URL", "https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com")
POLL_INTERVAL = int(os.getenv("MB_POLL_INTERVAL", "30"))

MB_AUTH_URL  = "https://id.mercedes-benz.com/as/authorization.oauth2"
MB_TOKEN_URL = "https://id.mercedes-benz.com/as/token.oauth2"
MB_API_BASE  = "https://api.mercedes-benz.com/vehicledata/v2"

TOKEN_FILE = Path(__file__).parent / ".mb_token.json"

SCOPES = " ".join([
    "mb:vehicle:mbdata:fuelstatus",
    "mb:vehicle:mbdata:vehiclestatus",
    "mb:vehicle:mbdata:vehiclelock",
    "mb:vehicle:mbdata:payasyoudrive",
])

DRY_RUN = False


# ═══ OAUTH2 ═══

def do_auth():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("ERROR: Set MB_CLIENT_ID and MB_CLIENT_SECRET in .env")
        sys.exit(1)

    url = (f"{MB_AUTH_URL}?response_type=code&client_id={CLIENT_ID}"
           f"&redirect_uri={REDIRECT_URI}&scope={SCOPES}")

    print(f"\n{'='*60}")
    print("MERCEDES-BENZ OAUTH2 AUTHORIZATION")
    print(f"{'='*60}")
    print(f"\nAfter you authorize, you'll be redirected to {REDIRECT_URI}")
    print("Copy the 'code' parameter from the URL.\n")

    webbrowser.open(url)
    print(f"If browser didn't open:\n{url}\n")
    code = input("Paste authorization code: ").strip()
    if not code:
        sys.exit("No code.")

    resp = requests.post(MB_TOKEN_URL, data={
        "grant_type": "authorization_code", "code": code,
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
    })
    if resp.status_code != 200:
        sys.exit(f"Token exchange failed: {resp.status_code}\n{resp.text}")

    td = resp.json()
    td["obtained_at"] = time.time()
    TOKEN_FILE.write_text(json.dumps(td, indent=2))
    os.chmod(TOKEN_FILE, 0o600)
    print(f"\n✓ Token saved to {TOKEN_FILE}")
    print(f"  expires_in: {td.get('expires_in', '?')}s")
    print(f"  refresh:    {'yes' if td.get('refresh_token') else 'NO'}")
    return td


def load_token():
    if not TOKEN_FILE.exists():
        sys.exit(f"No token. Run: python {sys.argv[0]} --auth")
    td = json.loads(TOKEN_FILE.read_text())
    if time.time() - td.get("obtained_at", 0) > (td.get("expires_in", 3600) - 300):
        td = refresh_token(td)
    return td


def refresh_token(td):
    rt = td.get("refresh_token")
    if not rt:
        sys.exit("No refresh token. Run --auth again.")
    resp = requests.post(MB_TOKEN_URL, data={
        "grant_type": "refresh_token", "refresh_token": rt,
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
    })
    if resp.status_code != 200:
        sys.exit(f"Refresh failed ({resp.status_code}). Run --auth.")
    nd = resp.json()
    nd["obtained_at"] = time.time()
    if "refresh_token" not in nd and rt:
        nd["refresh_token"] = rt
    TOKEN_FILE.write_text(json.dumps(nd, indent=2))
    os.chmod(TOKEN_FILE, 0o600)
    print("  (token refreshed)")
    return nd


# ═══ VEHICLE DATA ═══

def api_get(token, path):
    try:
        r = requests.get(f"{MB_API_BASE}{path}", headers={"Authorization": f"Bearer {token}"}, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"  API error: {e}")
    return None


def get_vehicles(token):
    return api_get(token, "/vehicles") or []


def get_status(token, vid):
    return api_get(token, f"/vehicles/{vid}/containers/vehiclestatus")


def get_lock(token, vid):
    return api_get(token, f"/vehicles/{vid}/containers/vehiclelock")


def get_fuel(token, vid):
    return api_get(token, f"/vehicles/{vid}/containers/fuelstatus")


def get_payg(token, vid):
    return api_get(token, f"/vehicles/{vid}/containers/payasyoudrive")


# ═══ CLOUDEVENT EMISSION ═══

def emit(event_type, data):
    if DRY_RUN:
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"  [{ts}] {event_type:.<24s} (dry run)")
        return

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    event = {
        "specversion": "1.0",
        "type": f"ohc.demo.vehicle.{event_type}",
        "source": "mercedes://relay",
        "id": f"mb-{event_type}-{uuid.uuid4().hex[:8]}",
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
    print(f"  [{ts}] {event_type:.<24s} {sym}")


def find_val(container, *needles):
    """Fish a value out of the MB API container response."""
    if not container:
        return None
    items = container if isinstance(container, list) else [container]
    for item in items:
        for needle in needles:
            if isinstance(item, dict):
                # Direct key match
                if needle in item:
                    v = item[needle]
                    return v.get("value", v) if isinstance(v, dict) else v
                # Nested in type field
                t = item.get("type", "")
                if needle.lower() in t.lower():
                    return item.get("value", item)
    return None


def redact_vid(vid):
    if len(vid) > 8:
        return vid[:4] + "..." + vid[-4:]
    return vid[:3] + "..."


# ═══ POLL CYCLE ═══

def poll(token, vid):
    rvid = redact_vid(vid)
    n = 0

    # Fuel
    fuel_data = get_fuel(token, vid)
    fl = find_val(fuel_data, "tanklevelpercent", "fuelLevel", "tanklevel")
    rng = find_val(fuel_data, "rangeliquid", "rangeLiquid", "range")
    if fl is not None:
        desc = f"Fuel: {fl}%"
        if rng is not None:
            desc += f" ({rng} km range)"
        emit("fuel", {"vehicle": rvid, "fuel_pct": fl, "range_km": rng, "description": desc})
        n += 1

    # Odometer
    payg = get_payg(token, vid)
    odo = find_val(payg, "odo", "odometer", "distanceSinceReset")
    if odo is not None:
        emit("odometer", {"vehicle": rvid, "odometer_km": odo, "description": f"Odometer: {odo} km"})
        n += 1

    # Lock status
    lock_data = get_lock(token, vid)
    lock = find_val(lock_data, "doorlockstatusvehicle", "vehicleLockStatus", "lockStatus")
    if lock is not None:
        locked = str(lock).lower() in ("0", "true", "locked", "1")
        emit("lock_status", {"vehicle": rvid, "locked": locked, "description": f"Vehicle {'locked' if locked else 'UNLOCKED'}"})
        n += 1

    # Vehicle status (tires, windows, etc.)
    vs = get_status(token, vid)
    tire = find_val(vs, "tirepressFrontLeft", "tirepressure")
    if tire is not None:
        emit("tire_pressure", {"vehicle": rvid, "front_left_kpa": tire, "description": f"Tire FL: {tire} kPa"})
        n += 1

    # Location — emit existence only, never coordinates
    if payg:
        lat = find_val(payg, "latitude")
        lon = find_val(payg, "longitude")
        if lat is not None and lon is not None:
            emit("location_ping", {"vehicle": rvid, "has_fix": True, "description": "Location updated (coords redacted)"})
            n += 1

    if n == 0:
        print("  (no data this cycle — API may need warmup or vehicle may be sleeping)")

    return n


# ═══ MAIN ═══

def run():
    td = load_token()
    token = td["access_token"]

    vid = VEHICLE_ID
    if not vid:
        print("No MB_VEHICLE_ID set. Discovering...")
        vehicles = get_vehicles(token)
        if isinstance(vehicles, list) and vehicles:
            vid = vehicles[0].get("id", vehicles[0].get("vin", ""))
            print(f"Found: {vid}")
        else:
            print(f"Response: {json.dumps(vehicles, indent=2)}")
            sys.exit("No vehicles found.")

    print(f"\n{'='*60}")
    print(f" MERCEDES → OHC RELAY")
    print(f"{'='*60}")
    print(f" Vehicle:   {redact_vid(vid)}")
    print(f" Target:    {NORTH_URL}/ingest")
    print(f" Interval:  {POLL_INTERVAL}s")
    print(f" Mode:      READ-ONLY {'(DRY RUN)' if DRY_RUN else ''}")
    print(f"{'='*60}\n")

    cycle = 0
    while True:
        try:
            cycle += 1
            print(f"── Poll #{cycle} ──")
            td = load_token()
            poll(td["access_token"], vid)
            print()
            time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            print("\n\nRelay stopped. 🚗")
            break
        except Exception as e:
            print(f"  ERROR: {e}")
            time.sleep(POLL_INTERVAL)


def main():
    global DRY_RUN
    p = argparse.ArgumentParser(description="Mercedes → OHC Relay")
    p.add_argument("--auth", action="store_true", help="OAuth2 flow")
    p.add_argument("--vehicles", action="store_true", help="List vehicles")
    p.add_argument("--status", action="store_true", help="One-shot status")
    p.add_argument("--dry-run", action="store_true", help="Don't POST")
    a = p.parse_args()

    if a.auth:
        do_auth(); return
    if a.vehicles:
        td = load_token()
        print(json.dumps(get_vehicles(td["access_token"]), indent=2)); return
    if a.status:
        td = load_token()
        vid = VEHICLE_ID or "unknown"
        for label, fn in [("fuel", get_fuel), ("lock", get_lock), ("status", get_status), ("payg", get_payg)]:
            print(f"\n── {label} ──")
            print(json.dumps(fn(td["access_token"], vid), indent=2, default=str))
        return
    if a.dry_run:
        DRY_RUN = True
    run()

if __name__ == "__main__":
    main()
