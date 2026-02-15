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
lock = threading.Lock()
POD_NAME = os.environ.get("HOSTNAME", "unknown")

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

