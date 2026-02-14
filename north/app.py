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



@app.get("/stage")
def stage():
    return f"""<!DOCTYPE html>
<html>
<head>
  <title>Stage Dashboard</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {{
      background:#111;
      color:#eee;
      font-family:system-ui;
      padding:2rem;
    }}
    #topbar {{
      display:flex;
      justify-content:space-between;
      align-items:center;
    }}
    #count {{
      font-size:8rem;
      font-weight:800;
      margin-top:2rem;
    }}
    button {{
      background:#222;
      color:#eee;
      border:1px solid #444;
      padding:0.5rem 1rem;
      cursor:pointer;
    }}
    button:hover {{
      background:#333;
    }}
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
    pre {{
      white-space:pre-wrap;
      font-size:0.85rem;
    }}
    .muted {{
      color:#777;
      font-size:0.85rem;
    }}
  </style>
</head>
<body>

  <div id="topbar">
    <h1>Stage Dashboard</h1>
    <button id="muteBtn">&#x1f50a; Sound ON</button>
  </div>

  <div id="count">0</div>

  <audio id="beep"
    src="/assets/Mario-coin-sound.mp3"
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
      <p>Pod: {POD_NAME}</p>
      <p class="muted">Live instance</p>
    </div>
  </div>

<script>
  const countEl = document.getElementById("count");
  const lastEl  = document.getElementById("last");
  const beep    = document.getElementById("beep");
  const muteBtn = document.getElementById("muteBtn");

  let muted = localStorage.getItem("muted") === "true";
  let audioUnlocked = false;

  function updateMuteUI() {{
    muteBtn.innerText = muted ? "\U0001f507 Muted" : "\U0001f50a Sound ON";
  }}

  muteBtn.onclick = async () => {{
    muted = !muted;
    localStorage.setItem("muted", muted);
    updateMuteUI();

    if (!audioUnlocked && !muted) {{
      try {{
        await beep.play();
        beep.pause();
        beep.currentTime = 0;
        audioUnlocked = true;
      }} catch (e) {{
        console.warn("audio unlock failed", e);
      }}
    }}
  }};

  updateMuteUI();

  const es = new EventSource("/events");

  es.onmessage = (e) => {{
    const d = JSON.parse(e.data);
    countEl.innerText = d.count;
    lastEl.innerText = JSON.stringify(d, null, 2);

    if (!muted && audioUnlocked) {{
      const chime = beep.cloneNode();
      chime.play().catch(() => {{}});
    }}
  }};
</script>

</body>
</html>"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

