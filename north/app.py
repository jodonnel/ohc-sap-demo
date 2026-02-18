from flask import Flask, request, Response, send_from_directory, redirect
from datetime import datetime, timezone
import json
import queue
import threading
import signal
import atexit
import os
import time
import subprocess

app = Flask(__name__)

# ── Build metadata ──
_start_time = time.time()
_git_commit = os.environ.get("GIT_COMMIT", "dev")
_build_version = os.environ.get("BUILD_VERSION", "local")

STATE_FILE = os.environ.get("STATE_FILE", "/data/state.json")
FLUSH_INTERVAL = int(os.environ.get("FLUSH_INTERVAL", "10"))

count = 0
last = {}
last_event_time = None
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
        "telemetry": telemetry, "last_event_time": last_event_time,
    }

def _restore(snap):
    global count, last, last_event_time, event_log, telemetry
    count = snap.get("count", 0)
    last = snap.get("last", {})
    last_event_time = snap.get("last_event_time")
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
    global count, last, last_event_time
    if request.method == "OPTIONS":
        return add_cors(Response(status=204))

    data = request.get_json(silent=True) or {}
    count += 1
    last_event_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
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

@app.get("/present-dtw")
def present_dtw():
    return send_from_directory("/stage", "present-dtw.html")

@app.get("/present-piport")
def present_piport():
    return send_from_directory("/stage", "present-piport.html")

@app.get("/labs")
def labs():
    return send_from_directory("/stage", "labs.html")

@app.get("/qr-present")
def qr_present():
    return send_from_directory("/stage", "qr-present.html")

@app.get("/about")
def about():
    uptime_s = int(time.time() - _start_time)
    h, rem = divmod(uptime_s, 3600)
    m, s = divmod(rem, 60)
    with lock:
        sse_clients = len(subscribers)
    return add_cors(Response(json.dumps({
        "version": _build_version,
        "commit": _git_commit,
        "pod": POD_NAME,
        "uptime": f"{h}h {m}m {s}s",
        "uptimeSeconds": uptime_s,
        "eventsProcessed": count,
        "lastEventTime": last_event_time,
        "sseClients": sse_clients,
        "stateFile": STATE_FILE,
    }), mimetype="application/json"))

@app.get("/about-panel")
def about_panel():
    return send_from_directory("/stage", "about.html")

@app.get("/healthz")
def healthz():
    return Response("ok", mimetype="text/plain")

@app.get("/readyz")
def readyz():
    ready = count >= 0  # always ready once loaded
    return Response("ready" if ready else "not ready",
                    status=200 if ready else 503,
                    mimetype="text/plain")

# ── Short URLs ──
# /go/<alias> redirects to the full path — for SMS, email, printed cards
SHORT_URLS = {
    "play":    "/play",
    "stage":   "/stage",
    "present": "/present",
    "dtw":     "/present-dtw",
    "rh":      "/present-rh",
    "about":   "/about-panel",
    "qr":      "/qr",
    "index":   "/present-index",
}

@app.get("/go/<alias>")
def short_url(alias):
    target = SHORT_URLS.get(alias.lower())
    if target:
        return redirect(target)
    return Response("Unknown short URL", status=404, mimetype="text/plain")

@app.get("/go")
def short_url_list():
    base = request.host_url.rstrip("/")
    lines = [f"{base}/go/{k}  →  {v}" for k, v in SHORT_URLS.items()]
    return Response("\n".join(["OHC Short URLs", "=" * 40] + lines),
                    mimetype="text/plain")

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

# ── Helper: emit a typed CloudEvent into the pipeline ──
def _emit(event_type, event_class, source, data):
    global count, last, last_event_time
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    with lock:
        count += 1
        last_event_time = ts
        payload = {"type": event_type, "eventclass": event_class, "source": source, "data": data}
        evt = {"ts": ts, "payload": payload, "count": count}
        last = evt
        event_log.append(evt)
        if len(event_log) > 200:
            event_log.pop(0)
        telemetry["event_classes"][event_class] = telemetry["event_classes"].get(event_class, 0) + 1
    publish(evt)
    return evt

# ── Contractor Overcharge State ──
_contractor_swipes = {}  # contractor_id → {"name", "swipes": [], "invoice_hours"}

# ── #42: 3D-GRC Kill Chain Scenario ──
@app.post("/scenario/grc-killchain")
def grc_killchain_scenario():
    body = request.get_json(silent=True) or {}
    delay = max(0.5, min(float(body.get("delay_s", 3)), 10.0))
    def run():
        _emit("ohc.demo.grc.badge_anomaly", "ohc.demo.grc", "alertenterprise-pacs",
              {"badge_id": "C-4471", "cardholder": "Contractor — Alex R.",
               "reader": "Server Room North", "anomaly": "cloned_badge",
               "flagged_by": "AlertEnterprise PACS", "confidence": 0.97})
        time.sleep(delay)
        _emit("ohc.demo.grc.it_lateral", "ohc.demo.grc", "sap-grc",
              {"source_ip": "10.12.44.71", "target": "SAP HANA DB",
               "credential": "svc-erp-admin", "erp_user": "C-4471-SVC",
               "correlated_badge": "C-4471", "sap_grc_alert": "AUT-2026-8812"})
        time.sleep(delay)
        _emit("ohc.demo.grc.ot_lockdown", "ohc.demo.grc", "ansible-automation",
              {"triggered_by": "SAP GRC + AlertEnterprise correlation",
               "scope": "OT Zone B — PLCs 12–19", "method": "Ansible playbook",
               "playbook": "ot-emergency-lockdown.yml", "plcs_isolated": 8, "latency_ms": 312})
    threading.Thread(target=run, daemon=True).start()
    return add_cors(Response(json.dumps({"ok": True, "scenario": "grc-killchain", "delay_s": delay}),
                             mimetype="application/json"))

@app.get("/present-grc")
def present_grc():
    return send_from_directory("/stage", "present-grc-killchain.html")

# ── #43: Shop-Floor Visual Inspection → SAP QM ──
@app.post("/shopfloor/defect")
def shopfloor_defect():
    d = request.get_json(silent=True) or {}
    lot = "QM-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    _emit("ohc.demo.shopfloor.defect_detected", "ohc.demo.shopfloor", "openshift-ai-edge",
          {"defect_type": d.get("defect_type", "surface_scratch"),
           "severity": d.get("severity", "minor"),
           "part_number": d.get("part_number", "PN-00442"),
           "line_id": d.get("line_id", "LINE-A3"),
           "inspection_lot": lot, "latency_ms": 487,
           "model": "defect-classifier-v2", "confidence": 0.94,
           "sap_qm_response": "Inspection lot " + lot + " created"})
    return add_cors(Response(json.dumps({"ok": True, "inspection_lot": lot, "latency_ms": 487}),
                             mimetype="application/json"))

@app.get("/present-shopfloor")
def present_shopfloor():
    return send_from_directory("/stage", "present-shopfloor.html")

# ── #44: Contractor Badge Swipe + Overcharge Check ──
@app.post("/contractor/swipe")
def contractor_swipe():
    d = request.get_json(silent=True) or {}
    cid = d.get("contractor_id", "C-4471")
    name = d.get("name", "Contractor " + cid)
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    with lock:
        if cid not in _contractor_swipes:
            _contractor_swipes[cid] = {"name": name, "swipes": []}
        _contractor_swipes[cid]["swipes"].append({"ts": ts, "direction": d.get("direction", "in"), "reader": d.get("reader", "Gate A")})
    _emit("ohc.demo.access.contractor_badge", "ohc.demo.access", "alertenterprise-pacs",
          {"contractor_id": cid, "name": name, "reader": d.get("reader", "Gate A"),
           "direction": d.get("direction", "in"), "swipe_count": len(_contractor_swipes[cid]["swipes"])})
    return add_cors(Response(json.dumps({"ok": True, "contractor_id": cid, "swipe_count": len(_contractor_swipes[cid]["swipes"])}),
                             mimetype="application/json"))

@app.post("/contractor/check-invoice")
def contractor_check_invoice():
    d = request.get_json(silent=True) or {}
    cid = d.get("contractor_id", "C-4471")
    invoice_hours = float(d.get("invoice_hours", 8.0))
    threshold = float(d.get("threshold", 1.0))
    if cid not in _contractor_swipes:
        return add_cors(Response(json.dumps({"ok": False, "error": "No swipe data for " + cid}), status=404, mimetype="application/json"))
    swipes = _contractor_swipes[cid]["swipes"]
    ins = sum(1 for s in swipes if s["direction"] == "in")
    outs = sum(1 for s in swipes if s["direction"] == "out")
    actual_hours = round(min(ins, outs) * 0.5, 2)
    discrepancy = round(invoice_hours - actual_hours, 2)
    result = {"contractor_id": cid, "invoice_hours": invoice_hours, "actual_hours": actual_hours,
              "discrepancy_hours": discrepancy, "flagged": abs(discrepancy) > threshold}
    if abs(discrepancy) > threshold:
        _emit("ohc.demo.grc.timesheet_discrepancy", "ohc.demo.grc", "sap-fieldglass",
              {**result, "action": "Timesheet flagged for rejection",
               "fieldglass_ticket": "FG-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")})
    return add_cors(Response(json.dumps({"ok": True, **result}), mimetype="application/json"))

@app.get("/contractor/state")
def contractor_state():
    return add_cors(Response(json.dumps(_contractor_swipes), mimetype="application/json"))

# ── #45: OpenBlue → SAP PM ──
@app.post("/openblue/fault")
def openblue_fault():
    d = request.get_json(silent=True) or {}
    wo = "WO-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    _emit("ohc.demo.openblue.asset_fault", "ohc.demo.openblue", "jci-openblue-bridge",
          {"asset_id": d.get("asset_id", "CHILLER-01"),
           "fault_code": d.get("fault_code", "TEMP_HIGH"),
           "zone": d.get("zone", "Building B — Mechanical Room"),
           "severity": d.get("severity", "critical"),
           "protocol": "BACnet", "sap_pm_work_order": wo,
           "routing": "OpenBlue → EIC → SAP PM"})
    return add_cors(Response(json.dumps({"ok": True, "work_order": wo}), mimetype="application/json"))

@app.get("/present-openblue")
def present_openblue():
    return send_from_directory("/stage", "present-openblue.html")

# ── #46: MII/ME Coexistence — Fan-out production order ──
@app.post("/shopfloor/production-order")
def shopfloor_production_order():
    d = request.get_json(silent=True) or {}
    oid = d.get("order_id", "PO-" + datetime.now(timezone.utc).strftime("%H%M%S"))
    mii_r = {"system": "SAP MII (legacy)", "status": "accepted", "latency_ms": 89, "order_id": oid}
    dm_r  = {"system": "SAP Digital Manufacturing", "status": "accepted", "latency_ms": 34, "order_id": oid}
    _emit("ohc.demo.shopfloor.production_order", "ohc.demo.shopfloor", "eic-fan-out",
          {"order_id": oid, "plant": d.get("plant", "PLANT_01"),
           "material": d.get("material", "MAT-00442"), "quantity": d.get("quantity", 100),
           "mii_response": mii_r, "sapdm_response": dm_r,
           "routing_mode": "coexistence", "both_systems_active": True})
    return add_cors(Response(json.dumps({"ok": True, "mii": mii_r, "sapdm": dm_r}), mimetype="application/json"))

# ── #47: OT Anomaly → SAP EAM ──
@app.post("/ot/anomaly")
def ot_anomaly():
    d = request.get_json(silent=True) or {}
    wo = "EAM-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    _emit("ohc.demo.ot.anomaly_detected", "ohc.demo.ot", "openshift-ai-substation",
          {"asset_id": d.get("asset_id", "XFMR-SUB-14"),
           "anomaly_type": d.get("anomaly_type", "voltage_spike"),
           "severity": d.get("severity", "high"),
           "sensor_reading": d.get("sensor_reading", 14200),
           "threshold": d.get("threshold", 13800),
           "ai_model": "anomaly-classifier-v1", "confidence": 0.91,
           "sap_eam_work_order": wo, "nerc_cip_zone": "Zone 3 — High Voltage",
           "routing": "OpenShift AI → EIC → SAP EAM"})
    return add_cors(Response(json.dumps({"ok": True, "work_order": wo}), mimetype="application/json"))

# ── #48: Consumer IoT — Withings + Garmin ──
@app.post("/ingest/withings")
def ingest_withings():
    d = request.get_json(silent=True) or {}
    measures = d.get("measures", [])
    weight_kg = measures[0].get("value", 82.3) if measures else d.get("weight", 82.3)
    _emit("ohc.demo.iot.biometric", "ohc.demo.iot", "withings-health-mate",
          {"device": "Withings Body+", "metric": "weight", "value_kg": weight_kg, "source": "withings"})
    return add_cors(Response(json.dumps({"ok": True, "metric": "weight", "value_kg": weight_kg}), mimetype="application/json"))

@app.post("/ingest/garmin")
def ingest_garmin():
    d = request.get_json(silent=True) or {}
    _emit("ohc.demo.iot.biometric", "ohc.demo.iot", "garmin-connect",
          {"device": "Garmin Venu 3", "heart_rate": d.get("heart_rate", 68),
           "steps": d.get("steps", 0), "stress_score": d.get("stress", 22), "source": "garmin"})
    return add_cors(Response(json.dumps({"ok": True, "heart_rate": d.get("heart_rate", 68)}), mimetype="application/json"))

# ── #49: Edge Vision — Blackjack ──
def _bj_total(cards):
    vals = []
    for c in cards:
        r = c[:-1] if len(c) > 1 else c
        vals.append(11 if r == "A" else 10 if r in ("J","Q","K") else int(r) if r.isdigit() else 10)
    t = sum(vals)
    while t > 21 and 11 in vals:
        vals[vals.index(11)] = 1; t = sum(vals)
    return t

def _bj_strategy(total, dealer):
    if total >= 17: return "STAND"
    if total <= 8: return "HIT"
    if total == 11: return "DOUBLE"
    if total == 10 and dealer <= 9: return "DOUBLE"
    if total >= 13 and dealer <= 6: return "STAND"
    return "HIT"

@app.post("/ingest/vision")
def ingest_vision():
    import time as _t
    t0 = _t.time()
    d = request.get_json(silent=True) or {}
    player_cards = d.get("player_cards", ["10H", "6S"])
    dealer_up = d.get("dealer_up", "7D")
    session_id = d.get("session_id", "bj-" + datetime.now(timezone.utc).strftime("%H%M%S"))
    total = _bj_total(player_cards)
    dealer_val = _bj_total([dealer_up])
    action = _bj_strategy(total, dealer_val)
    latency_ms = round((_t.time() - t0) * 1000 + 389)
    _emit("ohc.demo.vision.blackjack_decision", "ohc.demo.vision", "openshift-edge-ingest",
          {"session_id": session_id, "player_cards": player_cards, "player_total": total,
           "dealer_up": dealer_up, "action": action, "confidence": 0.94, "latency_ms": latency_ms,
           "pipeline": "Meta Glasses → OpenShift → BTP → earpiece"})
    return add_cors(Response(json.dumps({"ok": True, "cards": player_cards, "total": total,
                                         "action": action, "confidence": 0.94, "latency_ms": latency_ms}),
                             mimetype="application/json"))

@app.get("/present-blackjack")
def present_blackjack():
    return send_from_directory("/stage", "present-blackjack.html")

@app.get("/present-mii")
def present_mii():
    return send_from_directory("/stage", "present-mii.html")

@app.get("/present-substation")
def present_substation():
    return send_from_directory("/stage", "present-substation.html")

@app.post("/piport/idoc")
def piport_idoc():
    global count, last, last_event_time
    data = request.get_json(silent=True) or {}
    idoc_type = data.get("idoc_type", "MBGMCR002")
    plant = data.get("plant", "PLANT_01")
    material = data.get("material", "MAT-00001")
    quantity = data.get("quantity", 1)

    event = {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "payload": {
            "type": "ohc.demo.piport.idoc_goods_receipt",
            "eventclass": "ohc.demo.piport",
            "source": "pi-po-migration-factory",
            "data": {
                "idoc_type": idoc_type,
                "plant": plant,
                "material": material,
                "quantity": quantity,
                "routing_path": "PI/PO → EIC → S/4HANA",
                "eic_endpoint": "eic.ohc.demo.local",
                "s4_confirmation": "GR-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
                "latency_ms": 142,
            }
        }
    }
    event["payload"]["type"] = "ohc.demo.piport.idoc_goods_receipt"

    with lock:
        count += 1
        last_event_time = event["ts"]
        event["count"] = count
        last = {"ts": event["ts"], "payload": event["payload"], "count": count}
        event_log.append(last)
        if len(event_log) > 200:
            event_log.pop(0)
        ec = "ohc.demo.piport"
        telemetry["event_classes"][ec] = telemetry["event_classes"].get(ec, 0) + 1

    publish(last)
    return add_cors(Response(
        json.dumps({"ok": True, "idoc_type": idoc_type, "s4_confirmation": event["payload"]["data"]["s4_confirmation"]}),
        mimetype="application/json"
    ))

from alexa_skill import alexa_bp, init_alexa
app.register_blueprint(alexa_bp)

import sys
init_alexa(sys.modules[__name__])

load_state()
_flush_thread.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

