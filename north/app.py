from flask import Flask, request, Response, send_from_directory
from datetime import datetime, timezone
import json
import queue
import threading
import os

app = Flask(__name__)

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
    "devices": 0
}

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

    if "telemetry.battery" in evt_type:
        try:
            level = int(str(payload.get("level", "0")).replace("%", ""))
            telemetry["batteries"].append(level)
        except Exception:
            pass

    if "telemetry.network" in evt_type:
        net_type = payload.get("type", "unknown")
        telemetry["networks"][net_type] = telemetry["networks"].get(net_type, 0) + 1

    if "telemetry.locale" in evt_type:
        locale = payload.get("value", "unknown")
        telemetry["locales"][locale] = telemetry["locales"].get(locale, 0) + 1

    if "telemetry.device" in evt_type:
        telemetry["devices"] += 1

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

