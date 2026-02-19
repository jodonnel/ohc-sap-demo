from flask import Flask, request, Response, redirect
from datetime import datetime, timezone
import json
import threading
import signal
import atexit
import os
import time
import redis

app = Flask(__name__)

# Build metadata
_start_time = time.time()
_git_commit = os.environ.get("GIT_COMMIT", "dev")
_build_version = os.environ.get("BUILD_VERSION", "local")
POD_NAME = os.environ.get("HOSTNAME", "unknown")

# Redis connection
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_DB = int(os.environ.get("REDIS_DB", "0"))
REDIS_CHANNEL = os.environ.get("REDIS_CHANNEL", "ohc:events")

redis_client = None
pubsub = None
lock = threading.Lock()

def init_redis():
    """Initialize Redis connection."""
    global redis_client, pubsub
    try:
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_keepalive=True,
            health_check_interval=30
        )
        redis_client.ping()
        pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
        app.logger.info("Redis connected at %s:%d", REDIS_HOST, REDIS_PORT)
        return True
    except Exception as e:
        app.logger.error("Failed to connect to Redis: %s", e)
        return False

# Redis key helpers
def _count_key():
    return "ohc:count"

def _last_key():
    return "ohc:last"

def _last_event_time_key():
    return "ohc:last_event_time"

def _event_log_key():
    return "ohc:event_log"

def _telemetry_key(subkey):
    return f"ohc:telemetry:{subkey}"

def _contractor_key(contractor_id):
    return f"ohc:contractor:{contractor_id}"

def _contractor_swipes_key():
    return "ohc:contractor:swipes"

# State operations using Redis
def get_count():
    """Get current event count from Redis."""
    try:
        val = redis_client.get(_count_key())
        return int(val) if val else 0
    except Exception:
        return 0

def incr_count():
    """Increment and return event count."""
    try:
        return redis_client.incr(_count_key())
    except Exception:
        return 0

def set_last(event):
    """Store last event in Redis."""
    try:
        redis_client.set(_last_key(), json.dumps(event))
    except Exception as e:
        app.logger.warning("Failed to set last event: %s", e)

def get_last():
    """Get last event from Redis."""
    try:
        val = redis_client.get(_last_key())
        return json.loads(val) if val else {}
    except Exception:
        return {}

def set_last_event_time(ts):
    """Store last event timestamp."""
    try:
        redis_client.set(_last_event_time_key(), ts)
    except Exception:
        pass

def get_last_event_time():
    """Get last event timestamp."""
    try:
        return redis_client.get(_last_event_time_key())
    except Exception:
        return None

def append_event_log(event):
    """Append event to log (capped at 200)."""
    try:
        redis_client.lpush(_event_log_key(), json.dumps(event))
        redis_client.ltrim(_event_log_key(), 0, 199)
    except Exception as e:
        app.logger.warning("Failed to append event log: %s", e)

def get_event_log():
    """Get event log from Redis."""
    try:
        events = redis_client.lrange(_event_log_key(), 0, -1)
        return [json.loads(e) for e in events]
    except Exception:
        return []

def incr_telemetry_counter(key, field):
    """Increment a telemetry counter."""
    try:
        redis_client.hincrby(_telemetry_key(key), field, 1)
    except Exception:
        pass

def append_telemetry_list(key, value):
    """Append to a telemetry list."""
    try:
        redis_client.rpush(_telemetry_key(key), value)
    except Exception:
        pass

def get_telemetry_list(key):
    """Get telemetry list."""
    try:
        return redis_client.lrange(_telemetry_key(key), 0, -1)
    except Exception:
        return []

def get_telemetry_hash(key):
    """Get telemetry hash."""
    try:
        return redis_client.hgetall(_telemetry_key(key))
    except Exception:
        return {}

def get_telemetry_value(key):
    """Get single telemetry value."""
    try:
        val = redis_client.get(_telemetry_key(key))
        return int(val) if val else 0
    except Exception:
        return 0

def incr_telemetry_value(key):
    """Increment telemetry value."""
    try:
        return redis_client.incr(_telemetry_key(key))
    except Exception:
        return 0

def reset_telemetry():
    """Reset all telemetry data."""
    try:
        keys = redis_client.keys("ohc:telemetry:*")
        if keys:
            redis_client.delete(*keys)
    except Exception:
        pass

def reset_state():
    """Reset all state in Redis."""
    try:
        keys = redis_client.keys("ohc:*")
        if keys:
            redis_client.delete(*keys)
    except Exception as e:
        app.logger.warning("Failed to reset state: %s", e)

def publish(event):
    """Publish event to Redis pub/sub channel."""
    try:
        redis_client.publish(REDIS_CHANNEL, json.dumps(event))
    except Exception as e:
        app.logger.warning("Failed to publish event: %s", e)

def add_cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return resp

# SSE stream generator
def event_stream():
    """Generate SSE stream from Redis pub/sub."""
    sub = redis_client.pubsub(ignore_subscribe_messages=True)
    try:
        sub.subscribe(REDIS_CHANNEL)
        app.logger.info("SSE client subscribed to Redis channel")

        while True:
            try:
                message = sub.get_message(timeout=15)
                if message and message['type'] == 'message':
                    # Message data is already JSON string from publish()
                    yield f"data: {message['data']}\n\n"
                else:
                    # SSE heartbeat
                    yield ": keepalive\n\n"
            except Exception as e:
                app.logger.warning("SSE stream error: %s", e)
                break
    finally:
        sub.unsubscribe()
        sub.close()
        app.logger.info("SSE client unsubscribed")

@app.route("/state", methods=["GET", "OPTIONS"])
def state():
    if request.method == "OPTIONS":
        return add_cors(Response(status=204))
    return add_cors(Response(
        json.dumps({"count": get_count(), "last": get_last()}),
        mimetype="application/json"
    ))

@app.route("/ingest", methods=["POST", "OPTIONS"])
def ingest():
    if request.method == "OPTIONS":
        return add_cors(Response(status=204))

    data = request.get_json(silent=True) or {}
    count = incr_count()
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    set_last_event_time(ts)

    last = {
        "ts": ts,
        "payload": data,
        "count": count
    }

    set_last(last)
    publish(last)
    append_event_log(last)

    # Telemetry aggregation
    payload = data.get("data", data.get("payload", data))
    evt_type = data.get("type", "")
    evt_class = data.get("eventclass", "")

    if evt_class:
        incr_telemetry_counter("event_classes", evt_class)

    if "telemetry.battery" in evt_type or "telemetry.power_state" in evt_type:
        try:
            level = int(payload.get("batteryPct", payload.get("level", 0)))
            append_telemetry_list("batteries", str(level))
        except Exception:
            pass

    if "telemetry.network" in evt_type or "telemetry.network_env" in evt_type:
        net_type = payload.get("effectiveType", payload.get("type", "unknown"))
        incr_telemetry_counter("networks", net_type)

    if "telemetry.device" in evt_type or "telemetry.device_identity" in evt_type:
        incr_telemetry_value("devices")

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
                incr_telemetry_counter(key, val)

        langs = payload.get("languages", "")
        if langs:
            primary = langs.split(",")[0].strip()
            incr_telemetry_counter("locales", primary)

        profile = {
            "deviceClass": payload.get("deviceClass"),
            "os": payload.get("os"),
            "browser": payload.get("browser"),
            "tier": payload.get("tier"),
            "gpu": payload.get("gpuRenderer"),
            "cores": payload.get("cores"),
            "memory": payload.get("memoryGB"),
            "timezone": payload.get("timezone"),
        }
        append_telemetry_list("profiles", json.dumps(profile))
        redis_client.ltrim(_telemetry_key("profiles"), -50, -1)

    return add_cors(Response(
        json.dumps({"ok": True, "count": count}),
        mimetype="application/json"
    ))

@app.route("/events")
def events():
    resp = Response(event_stream(), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp

@app.get("/telemetry")
def get_telemetry():
    batteries = get_telemetry_list("batteries")
    battery_values = [int(b) for b in batteries if b]
    avg_battery = round(sum(battery_values) / max(1, len(battery_values))) if battery_values else 0

    profiles = get_telemetry_list("profiles")
    profiles_parsed = []
    for p in profiles[-10:]:
        try:
            profiles_parsed.append(json.loads(p))
        except Exception:
            pass

    return add_cors(Response(json.dumps({
        "avgBattery": avg_battery,
        "batteryCount": len(battery_values),
        "networks": get_telemetry_hash("networks"),
        "locales": get_telemetry_hash("locales"),
        "devices": get_telemetry_value("devices"),
        "deviceClasses": get_telemetry_hash("device_classes"),
        "tiers": get_telemetry_hash("tiers"),
        "osFamilies": get_telemetry_hash("os_families"),
        "browsers": get_telemetry_hash("browsers"),
        "gpus": get_telemetry_hash("gpus"),
        "timezones": get_telemetry_hash("timezones"),
        "profiles": profiles_parsed,
        "eventClasses": get_telemetry_hash("event_classes"),
    }), mimetype="application/json"))

@app.get("/log")
def event_log_view():
    return add_cors(Response(json.dumps(get_event_log()), mimetype="application/json"))

@app.get("/pod-name")
def pod_name():
    return add_cors(Response(json.dumps({"pod": POD_NAME}), mimetype="application/json"))

@app.get("/about")
def about():
    uptime_s = int(time.time() - _start_time)
    h, rem = divmod(uptime_s, 3600)
    m, s = divmod(rem, 60)

    return add_cors(Response(json.dumps({
        "version": _build_version,
        "commit": _git_commit,
        "pod": POD_NAME,
        "uptime": f"{h}h {m}m {s}s",
        "uptimeSeconds": uptime_s,
        "eventsProcessed": get_count(),
        "lastEventTime": get_last_event_time(),
        "redisHost": REDIS_HOST,
        "redisPort": REDIS_PORT,
    }), mimetype="application/json"))

@app.get("/healthz")
def healthz():
    return Response("ok", mimetype="text/plain")

@app.get("/health")
def health():
    """Health check with Redis connectivity check."""
    try:
        redis_client.ping()
        return Response(
            json.dumps({"status": "healthy", "redis": "connected"}),
            status=200,
            mimetype="application/json"
        )
    except Exception as e:
        return Response(
            json.dumps({"status": "unhealthy", "redis": "disconnected", "error": str(e)}),
            status=503,
            mimetype="application/json"
        )

@app.get("/readyz")
def readyz():
    try:
        redis_client.ping()
        return Response("ready", status=200, mimetype="text/plain")
    except Exception:
        return Response("not ready", status=503, mimetype="text/plain")

# Short URLs
SHORT_URLS = {
    "play": "/play",
    "stage": "/stage",
    "present": "/present",
    "dtw": "/present-dtw",
    "rh": "/present-rh",
    "about": "/about-panel",
    "qr": "/qr",
    "index": "/present-index",
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
def reset_state_endpoint():
    reset_state()
    return add_cors(Response(json.dumps({"ok": True, "reset": True}), mimetype="application/json"))

# Helper: emit a typed CloudEvent into the pipeline
def _emit(event_type, event_class, source, data):
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    count = incr_count()
    set_last_event_time(ts)

    payload = {"type": event_type, "eventclass": event_class, "source": source, "data": data}
    evt = {"ts": ts, "payload": payload, "count": count}

    set_last(evt)
    append_event_log(evt)
    incr_telemetry_counter("event_classes", event_class)

    publish(evt)
    return evt

# #42: 3D-GRC Kill Chain Scenario
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

# #43: Shop-Floor Visual Inspection → SAP QM
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

# #44: Contractor Badge Swipe + Overcharge Check
@app.post("/contractor/swipe")
def contractor_swipe():
    d = request.get_json(silent=True) or {}
    cid = d.get("contractor_id", "C-4471")
    name = d.get("name", "Contractor " + cid)
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Store swipe in Redis
    swipe_data = {"ts": ts, "direction": d.get("direction", "in"), "reader": d.get("reader", "Gate A")}
    redis_client.rpush(_contractor_key(cid), json.dumps(swipe_data))
    redis_client.hset(_contractor_swipes_key(), cid, name)

    swipe_count = redis_client.llen(_contractor_key(cid))

    _emit("ohc.demo.access.contractor_badge", "ohc.demo.access", "alertenterprise-pacs",
          {"contractor_id": cid, "name": name, "reader": d.get("reader", "Gate A"),
           "direction": d.get("direction", "in"), "swipe_count": swipe_count})

    return add_cors(Response(json.dumps({"ok": True, "contractor_id": cid, "swipe_count": swipe_count}),
                             mimetype="application/json"))

@app.post("/contractor/check-invoice")
def contractor_check_invoice():
    d = request.get_json(silent=True) or {}
    cid = d.get("contractor_id", "C-4471")
    invoice_hours = float(d.get("invoice_hours", 8.0))
    threshold = float(d.get("threshold", 1.0))

    if not redis_client.exists(_contractor_key(cid)):
        return add_cors(Response(json.dumps({"ok": False, "error": "No swipe data for " + cid}),
                                status=404, mimetype="application/json"))

    swipes_raw = redis_client.lrange(_contractor_key(cid), 0, -1)
    swipes = [json.loads(s) for s in swipes_raw]

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
    contractor_names = redis_client.hgetall(_contractor_swipes_key())
    state = {}

    for cid, name in contractor_names.items():
        swipes_raw = redis_client.lrange(_contractor_key(cid), 0, -1)
        swipes = [json.loads(s) for s in swipes_raw]
        state[cid] = {"name": name, "swipes": swipes}

    return add_cors(Response(json.dumps(state), mimetype="application/json"))

# #45: OpenBlue → SAP PM
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

# #46: MII/ME Coexistence — Fan-out production order
@app.post("/shopfloor/production-order")
def shopfloor_production_order():
    d = request.get_json(silent=True) or {}
    oid = d.get("order_id", "PO-" + datetime.now(timezone.utc).strftime("%H%M%S"))
    mii_r = {"system": "SAP MII (legacy)", "status": "accepted", "latency_ms": 89, "order_id": oid}
    dm_r = {"system": "SAP Digital Manufacturing", "status": "accepted", "latency_ms": 34, "order_id": oid}
    _emit("ohc.demo.shopfloor.production_order", "ohc.demo.shopfloor", "eic-fan-out",
          {"order_id": oid, "plant": d.get("plant", "PLANT_01"),
           "material": d.get("material", "MAT-00442"), "quantity": d.get("quantity", 100),
           "mii_response": mii_r, "sapdm_response": dm_r,
           "routing_mode": "coexistence", "both_systems_active": True})
    return add_cors(Response(json.dumps({"ok": True, "mii": mii_r, "sapdm": dm_r}), mimetype="application/json"))

# #47: OT Anomaly → SAP EAM
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

# #48: Consumer IoT — Withings + Garmin
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

# #49: Edge Vision — Blackjack
def _bj_total(cards):
    vals = []
    for c in cards:
        r = c[:-1] if len(c) > 1 else c
        vals.append(11 if r == "A" else 10 if r in ("J", "Q", "K") else int(r) if r.isdigit() else 10)
    t = sum(vals)
    while t > 21 and 11 in vals:
        vals[vals.index(11)] = 1
        t = sum(vals)
    return t

def _bj_strategy(total, dealer):
    if total >= 17:
        return "STAND"
    if total <= 8:
        return "HIT"
    if total == 11:
        return "DOUBLE"
    if total == 10 and dealer <= 9:
        return "DOUBLE"
    if total >= 13 and dealer <= 6:
        return "STAND"
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

# PI/PO IDoc endpoint
@app.post("/piport/idoc")
def piport_idoc():
    data = request.get_json(silent=True) or {}
    idoc_type = data.get("idoc_type", "MBGMCR002")
    plant = data.get("plant", "PLANT_01")
    material = data.get("material", "MAT-00001")
    quantity = data.get("quantity", 1)

    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    count = incr_count()
    set_last_event_time(ts)

    payload = {
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

    evt = {"ts": ts, "payload": payload, "count": count}
    set_last(evt)
    append_event_log(evt)
    incr_telemetry_counter("event_classes", "ohc.demo.piport")
    publish(evt)

    return add_cors(Response(
        json.dumps({"ok": True, "idoc_type": idoc_type, "s4_confirmation": payload["data"]["s4_confirmation"]}),
        mimetype="application/json"
    ))

# Badge tap endpoint
@app.post("/badge/tap")
def badge_tap():
    """Handle badge tap events."""
    data = request.get_json(silent=True) or {}
    badge_id = data.get("badge_id", "unknown")
    reader_id = data.get("reader_id", "unknown")

    _emit("ohc.demo.access.badge_tap", "ohc.demo.access", "badge-reader",
          {"badge_id": badge_id, "reader_id": reader_id})

    return add_cors(Response(json.dumps({"ok": True}), mimetype="application/json"))

# Initialize Redis on startup
init_redis()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
