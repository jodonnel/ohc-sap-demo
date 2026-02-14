from flask import Flask, request, Response
from datetime import datetime
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
                event = q.get()
                yield f"data: {json.dumps(event)}\n\n"
        except GeneratorExit:
            with lock:
                subscribers.remove(q)

    return Response(stream(), mimetype="text/event-stream")

@app.get("/stage")
def stage():
    return f"""<!DOCTYPE html>
<html>
<head>
  <title>Stage Dashboard — SSE</title>
  <style>
    body {{ background:#111; color:#eee; font-family:system-ui; padding:2rem }}
    #count {{ font-size:8rem; font-weight:800 }}
    .tiles {{
      display:grid;
      grid-template-columns: repeat(auto-fit, minmax(220px,1fr));
      gap:1rem;
      margin-top:2rem;
    }}
    .tile {{
      background:#181818;
      border:1px solid #333;
      padding:1rem;
    }}
    .tile h3 {{
      margin-top:0;
      font-size:1rem;
      color:#aaa;
    }}
    .tile pre {{
      white-space:pre-wrap;
      font-size:0.85rem;
    }}
    .muted {{
      color:#777;
      font-size:0.85rem;
    }}
    .notes {{
      margin-top:2rem;
      padding:1rem;
      border:1px solid #333;
      background:#181818;
      font-size:0.95rem;
      max-width:720px;
    }}
    .notes h2 {{ margin-top:0; font-size:1.1rem; }}
    .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
  </style>
</head>
<body>
  <h1>Stage Dashboard</h1>
  <div id="count">0</div>

  <audio id="beep"
    src="https://actions.google.com/sounds/v1/cartoon/coin_collect.ogg"
    preload="auto"></audio>

  <div class="tiles">
    <div class="tile">
      <h3>Last Event</h3>
      <pre id="last">—</pre>
    </div>

    <div class="tile">
      <h3>Transport</h3>
      <p><strong>SSE</strong> (push)</p>
      <p class="muted">Polling disabled</p>
    </div>

    <div class="tile">
      <h3>Runtime</h3>
      <p>Pod: <span id="pod">{POD_NAME}</span></p>
      <p class="muted">Live instance</p>
    </div>

    <div class="tile">
      <h3>Boundary</h3>
      <p>Edge → North</p>
      <p class="muted">Pre-EIC stage</p>
    </div>
  </div>

  <div class="notes">
    <h2>Runtime Notes</h2>
    <ul>
      <li><strong>Polling removed.</strong> This page no longer calls <span class="mono">/state</span>.</li>
      <li><strong>Server-Sent Events (SSE) enabled.</strong> Updates are pushed via <span class="mono">GET /events</span>.</li>
      <li>UI updates occur <em>only</em> when new events are ingested.</li>
      <li>This page documents the live runtime behavior.</li>
    </ul>
  </div>

  <script>
    const countEl = document.getElementById("count");
    const lastEl = document.getElementById("last");
    const beep = document.getElementById("beep");

    const es = new EventSource("/events");

    es.onmessage = (e) => {{
      const d = JSON.parse(e.data);
      countEl.innerText = d.count;
      lastEl.innerText = JSON.stringify(d, null, 2);
      beep.play().catch(()=>{{}});
    }};
  </script>
</body>
</html>"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
