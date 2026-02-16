from flask import Flask, request, Response, send_from_directory
from datetime import datetime, timezone
import json
import queue
import threading
import signal
import atexit
import os

app = Flask(__name__)

STATE_FILE = os.environ.get("STATE_FILE", "/data/state.json")
FLUSH_INTERVAL = int(os.environ.get("FLUSH_INTERVAL", "10"))

count = 0
last = {}
subscribers = []
event_log = []
lock = threading.Lock()
POD_NAME = os.environ.get("HOSTNAME", "unknown")

telemetry = {
    "batteries": [],
    "networks": {},
    "locales": {},
    "devices": 0,
    "device_classes": {},
    "tiers": {},
    "os_families": {},
    "browsers": {},
    "gpus": {},
    "timezones": {},
    "profiles": [],
    "event_classes": {},
}

# ── State persistence ──
def _snapshot():
    return {
        "count": count, "last": last, "event_log": event_log,
        "telemetry": telemetry,
    }

def _restore(snap):
    global count, last, event_log, telemetry
    count = snap.get("count", 0)
    last = snap.get("last", {})
    event_log[:] = snap.get("event_log", [])
    saved_telem = snap.get("telemetry", {})
    for k in telemetry:
        if k in saved_telem:
            if isinstance(telemetry[k], list):
                telemetry[k][:] = saved_telem[k]
            elif isinstance(telemetry[k], dict):
                telemetry[k].clear()
                telemetry[k].update(saved_telem[k])
            else:
                telemetry[k] = saved_telem[k]

def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            _restore(json.load(f))
        app.logger.info("Restored state from %s (count=%d)", STATE_FILE, count)
    except FileNotFoundError:
        app.logger.info("No state file at %s — starting fresh", STATE_FILE)
    except Exception as e:
        app.logger.warning("Failed to load state: %s — starting fresh", e)

def flush_state():
    try:
        os.makedirs(os.path.dirname(STATE_FILE) or ".", exist_ok=True)
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(_snapshot(), f)
        os.replace(tmp, STATE_FILE)
    except Exception as e:
        app.logger.warning("Failed to flush state: %s", e)

def _flush_loop():
    while True:
        threading.Event().wait(FLUSH_INTERVAL)
        with lock:
            flush_state()

_flush_thread = threading.Thread(target=_flush_loop, daemon=True)

def _shutdown_flush(*_):
    with lock:
        flush_state()
    app.logger.info("State flushed on shutdown")

atexit.register(_shutdown_flush)
signal.signal(signal.SIGTERM, lambda *_: (_shutdown_flush(), exit(0)))

def add_cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return resp

def publish(event):
    with lock:
        for q in list(subscribers):
            q.put(event)


@app.route("/assets/<path:filename>")
def assets(filename):
    return send_from_directory("/assets", filename)



@app.route("/state", methods=["GET","OPTIONS"])
def state():
    if request.method == "OPTIONS":
        return add_cors(Response(status=204))
    return add_cors(Response(
        json.dumps({"count": count, "last": last}),
        mimetype="application/json"
    ))

@app.route("/ingest", methods=["POST","OPTIONS"])
def ingest():
    global count, last
    if request.method == "OPTIONS":
        return add_cors(Response(status=204))

    data = request.get_json(silent=True) or {}
    count += 1
    last = {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "payload": data,
        "count": count
    }

    publish(last)

    event_log.append(last)
    if len(event_log) > 200:
        event_log.pop(0)

    # Telemetry aggregation
    payload = data.get("data", data.get("payload", data))
    evt_type = data.get("type", "")
    evt_class = data.get("eventclass", "")
    if evt_class:
        telemetry["event_classes"][evt_class] = telemetry["event_classes"].get(evt_class, 0) + 1

    if "telemetry.battery" in evt_type or "telemetry.power_state" in evt_type:
        try:
            level = int(payload.get("batteryPct", payload.get("level", 0)))
            telemetry["batteries"].append(level)
        except Exception:
            pass

    if "telemetry.network" in evt_type or "telemetry.network_env" in evt_type:
        net_type = payload.get("effectiveType", payload.get("type", "unknown"))
        telemetry["networks"][net_type] = telemetry["networks"].get(net_type, 0) + 1

    if "telemetry.device" in evt_type or "telemetry.device_identity" in evt_type:
        telemetry["devices"] += 1
        # Aggregate by class, tier, OS, browser, GPU, timezone
        for key, field in [
            ("device_classes", "deviceClass"),
            ("tiers", "tier"),
            ("os_families", "os"),
            ("browsers", "browser"),
            ("gpus", "gpuRenderer"),
            ("timezones", "timezone"),
        ]:
            val = payload.get(field, "unknown")
            if val and val != "unknown" and val != "unavailable":
                telemetry[key][val] = telemetry[key].get(val, 0) + 1
        # Also capture languages as locale
        langs = payload.get("languages", "")
        if langs:
            primary = langs.split(",")[0].strip()
            telemetry["locales"][primary] = telemetry["locales"].get(primary, 0) + 1
        # Store full profile (cap at 50)
        telemetry["profiles"].append({
            "deviceClass": payload.get("deviceClass"),
            "os": payload.get("os"),
            "browser": payload.get("browser"),
            "tier": payload.get("tier"),
            "gpu": payload.get("gpuRenderer"),
            "cores": payload.get("cores"),
            "memory": payload.get("memoryGB"),
            "timezone": payload.get("timezone"),
        })
        if len(telemetry["profiles"]) > 50:
            telemetry["profiles"].pop(0)

    return add_cors(Response(
        json.dumps({"ok": True, "count": count}),
        mimetype="application/json"
    ))



@app.route("/events")
def events():
    q = queue.Queue()
    with lock:
        subscribers.append(q)

    def stream():
        try:
            while True:
                try:
                    event = q.get(timeout=15)
                    yield f"data: {json.dumps(event)}\n\n"
                except queue.Empty:
                    # SSE heartbeat (comment)
                    yield ": keepalive\n\n"
        finally:
            with lock:
                subscribers.remove(q)

    resp = Response(stream(), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp



@app.get("/telemetry")
def get_telemetry():
    avg_battery = round(sum(telemetry["batteries"]) / max(1, len(telemetry["batteries"])))
    return add_cors(Response(json.dumps({
        "avgBattery": avg_battery,
        "batteryCount": len(telemetry["batteries"]),
        "networks": telemetry["networks"],
        "locales": telemetry["locales"],
        "devices": telemetry["devices"],
        "deviceClasses": telemetry["device_classes"],
        "tiers": telemetry["tiers"],
        "osFamilies": telemetry["os_families"],
        "browsers": telemetry["browsers"],
        "gpus": telemetry["gpus"],
        "timezones": telemetry["timezones"],
        "profiles": telemetry["profiles"][-10:],
        "eventClasses": telemetry["event_classes"],
    }), mimetype="application/json"))

@app.get("/log")
def event_log_view():
    return add_cors(Response(json.dumps(event_log), mimetype="application/json"))

@app.get("/pod-name")
def pod_name():
    return add_cors(Response(json.dumps({"pod": POD_NAME}), mimetype="application/json"))

@app.get("/stage")
def stage():
    return send_from_directory("/stage", "dashboard.html")

@app.get("/play")
def play():
    return send_from_directory("/south-ui", "index.html")

@app.get("/qr")
def qr():
    return send_from_directory("/stage", "qr.html")

@app.get("/present")
def present():
    return send_from_directory("/stage", "present.html")

@app.get("/present-rh")
def present_rh():
    return send_from_directory("/stage", "present-rh.html")

@app.get("/present-util")
def present_util():
    return send_from_directory("/stage", "present-util.html")

@app.get("/present-rail")
def present_rail():
    return send_from_directory("/stage", "present-rail.html")

@app.get("/present-ad")
def present_ad():
    return send_from_directory("/stage", "present-ad.html")

@app.get("/present-index")
def present_index():
    return send_from_directory("/stage", "present-index.html")

@app.get("/qr-present")
def qr_present():
    return send_from_directory("/stage", "qr-present.html")

@app.post("/reset")
def reset_state():
    global count, last
    with lock:
        count = 0
        last = {}
        event_log.clear()
        for k in telemetry:
            if isinstance(telemetry[k], list):
                telemetry[k].clear()
            elif isinstance(telemetry[k], dict):
                telemetry[k].clear()
            else:
                telemetry[k] = 0
        try:
            os.remove(STATE_FILE)
        except FileNotFoundError:
            pass
    return add_cors(Response(json.dumps({"ok": True, "reset": True}), mimetype="application/json"))

load_state()
_flush_thread.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

