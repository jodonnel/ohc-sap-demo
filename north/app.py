from flask import Flask, request, Response, send_from_directory
from datetime import datetime
import json
import queue
import threading
import os
import time
import queue

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
        "ts": datetime.utcnow().isoformat() + "Z",
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



@app.get("/stage")
def stage():
    return """<!DOCTYPE html>
<html>
<head>
  <title>Stage Dashboard</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
   html, body {
        margin: 0;
        padding: 1.5rem;
        background: #0b0b0b;
        color: #e6e6e6;
        font-family: system-ui, -apple-system, BlinkMacSystemFont;
    }

    h1 {
        font-weight: 500;
        letter-spacing: 0.04em;
        margin-bottom: 1rem;
        }

    .app {
        min-height: 100vh;
    }

    .grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 1rem;
    }

    .tile {
        background: #151515;
        border: 1px solid #2a2a2a;
        border-radius: 14px;
        padding: 1.25rem;
    }

    .counter {
        font-size: 3rem;
        font-weight: 600;
        color: #ff3b3b;
    }

    .label {
        opacity: 0.6;
        font-size: 0.9rem;
        margin-bottom: 0.25rem;
    }

    .meta {
        position: fixed;
        bottom: 10px;
        right: 14px;
        font-size: 11px;
        opacity: 0.4;
    }
    </style>



</head>










<body>
  <div class="app">
    <h1>NORTH · LIVE</h1>

  <div class="grid">
    <div class="tile">
      <div class="label">Total events</div>
      <div id="count" class="counter">0</div>
    </div>

    <div class="tile">
      <div class="label">Last event</div>
      <div id="last">—</div>
    </div>

    <div class="tile">
      <div class="label">Source</div>
      <div id="source">—</div>
    </div>
  </div>

  <div class="meta">
    north-app · live · <span id="ts"></span>
  </div>




<script>
  const countEl = document.getElementById("count");
  const lastEl  = document.getElementById("last");

  const es = new EventSource("/events");

  es.onmessage = (e) => {
    const d = JSON.parse(e.data);
    countEl.innerText = d.count;
    lastEl.innerText = d.ts;


  };
</script>

    </div>

</body>
</html>"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

