"""
Alexa Custom Skill — "Building Ops" — Option A (Full Integration)

This is a Flask blueprint that handles Alexa skill requests.
It runs INSIDE north/app.py on the same OpenShift cluster.

Alexa sends POST /alexa with JSON, we respond with speech.

Intents:
  - StatusIntent:    "Alexa, ask building ops for a status report"
  - DevicesIntent:   "Alexa, ask building ops how many devices are connected"
  - RateIntent:      "Alexa, ask building ops what's the event rate"
  - LockdownIntent:  "Alexa, tell building ops to initiate lockdown"
  - ResetIntent:     "Alexa, tell building ops to reset the count"

Setup:
  1. Add this blueprint to north/app.py
  2. Create Alexa skill at developer.amazon.com
  3. Set endpoint to: https://north-qr-demo-qa.apps.cluster-nlthm.nlthm.sandbox3528.opentlc.com/alexa
  4. SSL: "My development endpoint is a sub-domain of a domain that has a wildcard certificate"
  5. Copy interaction_model.json into the Alexa console JSON editor
  6. Build + test

Note: For dev/demo use, we skip Alexa request signature verification.
      For production/certification, add ask-sdk-webservice-support.
"""

from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
import json
import uuid

alexa_bp = Blueprint('alexa', __name__)

# Ref to app module globals — set by init_alexa() after blueprint registration
_app = None

def init_alexa(app_module):
    """Store reference to app module globals. Call after register_blueprint."""
    global _app
    _app = app_module


# ═══════════════════════════════════════════
# RESPONSE HELPERS
# ═══════════════════════════════════════════
def alexa_response(speech, should_end=True, card_title=None, card_text=None):
    """Build a standard Alexa JSON response."""
    resp = {
        "version": "1.0",
        "response": {
            "outputSpeech": {
                "type": "PlainText",
                "text": speech
            },
            "shouldEndSession": should_end
        }
    }
    if card_title:
        resp["response"]["card"] = {
            "type": "Simple",
            "title": card_title,
            "content": card_text or speech
        }
    return jsonify(resp)


def alexa_error(speech="Sorry, something went wrong."):
    return alexa_response(speech, should_end=True)


# ═══════════════════════════════════════════
# MAIN ROUTE
# ═══════════════════════════════════════════
@alexa_bp.route('/alexa', methods=['POST'])
def alexa_handler():
    """Handle all Alexa skill requests."""
    try:
        body = request.get_json(force=True)
    except Exception:
        return alexa_error()

    req_type = body.get("request", {}).get("type", "")

    # ─── LaunchRequest ───
    if req_type == "LaunchRequest":
        return handle_launch()

    # ─── IntentRequest ───
    elif req_type == "IntentRequest":
        intent_name = body["request"]["intent"]["name"]

        if intent_name == "StatusIntent":
            return handle_status()
        elif intent_name == "DevicesIntent":
            return handle_devices()
        elif intent_name == "RateIntent":
            return handle_rate()
        elif intent_name == "LockdownIntent":
            return handle_lockdown()
        elif intent_name == "ResetIntent":
            return handle_reset()
        elif intent_name in ("AMAZON.HelpIntent",):
            return handle_help()
        elif intent_name in ("AMAZON.CancelIntent", "AMAZON.StopIntent"):
            return alexa_response("Building ops signing off.")
        elif intent_name == "AMAZON.FallbackIntent":
            return alexa_response(
                "I didn't catch that. Try asking for a status report, "
                "device count, or event rate."
            )
        else:
            return alexa_error(f"I don't know how to handle {intent_name}.")

    # ─── SessionEndedRequest ───
    elif req_type == "SessionEndedRequest":
        return alexa_response("", should_end=True)

    return alexa_error()


# ═══════════════════════════════════════════
# INTENT HANDLERS
# ═══════════════════════════════════════════

def _get_state():
    """Read demo state directly from app.py globals (same process)."""
    return {"count": _app.count, "last": _app.last}


def _get_telemetry():
    """Read telemetry directly from app.py globals (same process)."""
    t = _app.telemetry
    avg = round(sum(t["batteries"]) / max(1, len(t["batteries"]))) if t["batteries"] else 0
    return {"devices": t["devices"], "avgBattery": avg,
            "networks": t["networks"], "locales": t["locales"]}


def handle_launch():
    state = _get_state()
    count = state.get("count", 0)
    speech = (
        f"Building ops online. "
        f"The nervous system has processed {count} events so far. "
        f"Ask me for a status report, device count, or event rate."
    )
    return alexa_response(speech, should_end=False,
                         card_title="Building Ops",
                         card_text=f"Events: {count}")


def handle_status():
    state = _get_state()
    telem = _get_telemetry()
    count = state.get("count", 0)
    devices = telem.get("devices", 0)

    if count == 0:
        speech = "The nervous system is quiet. No events recorded yet. Waiting for nerve impulses."
    elif count < 100:
        speech = (
            f"The nervous system is warming up. "
            f"{count} nerve impulses from {devices} devices. "
            f"Still ramping."
        )
    elif count < 500:
        speech = (
            f"The nervous system is active. "
            f"{count} nerve impulses from {devices} devices. "
            f"Signals are flowing through the spinal cord."
        )
    else:
        speech = (
            f"The nervous system is fully online. "
            f"{count} nerve impulses from {devices} devices. "
            f"Every signal is reaching the brain."
        )

    return alexa_response(speech,
                         card_title="Status Report",
                         card_text=f"Events: {count} | Devices: {devices}")


def handle_devices():
    telem = _get_telemetry()
    devices = telem.get("devices", 0)

    if devices == 0:
        speech = "No devices connected yet. Scan the Q R code to become a nerve ending."
    elif devices == 1:
        speech = "One device connected. One nerve ending sending impulses."
    else:
        speech = f"{devices} devices connected. {devices} nerve endings sending impulses to the spinal cord."

    return alexa_response(speech,
                         card_title="Connected Devices",
                         card_text=f"Devices: {devices}")


def handle_rate():
    state = _get_state()
    # Rate isn't stored server-side in the current design,
    # but we can estimate from recent events
    count = state.get("count", 0)
    speech = (
        f"The nervous system has processed {count} total events. "
        f"Check the dashboard for the live rate."
    )
    return alexa_response(speech,
                         card_title="Event Rate",
                         card_text=f"Total events: {count}")


def handle_lockdown():
    """Inject a lockdown command CloudEvent directly — motor command DOWN."""
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    _app.count += 1
    _app.last_event_time = now
    event_payload = {
        "ts": now,
        "payload": {
            "specversion": "1.0",
            "type": "ohc.demo.command.lockdown",
            "source": "alexa://building-ops",
            "id": f"alexa-lockdown-{uuid.uuid4().hex[:8]}",
            "time": now,
            "eventclass": "command",
            "data": {
                "action": "lockdown",
                "initiated_by": "alexa_voice_command",
                "description": "Lockdown initiated via Alexa voice command",
            },
        },
        "count": _app.count,
    }
    _app.last = event_payload
    _app.event_log.append(event_payload)
    if len(_app.event_log) > 200:
        _app.event_log.pop(0)
    _app.telemetry["event_classes"]["command"] = _app.telemetry["event_classes"].get("command", 0) + 1
    _app.publish(event_payload)

    speech = (
        "Lockdown initiated. Command event sent through the spinal cord. "
        "All access points notified. Motor command sent."
    )
    return alexa_response(speech,
                         card_title="Lockdown",
                         card_text="Motor command: lockdown initiated via Alexa")


def handle_reset():
    """Reset all state directly via app globals."""
    import os
    with _app.lock:
        _app.count = 0
        _app.last = {}
        _app.last_event_time = None
        _app.event_log.clear()
        for k in _app.telemetry:
            if isinstance(_app.telemetry[k], list):
                _app.telemetry[k].clear()
            elif isinstance(_app.telemetry[k], dict):
                _app.telemetry[k].clear()
            else:
                _app.telemetry[k] = 0
        try:
            os.remove(_app.STATE_FILE)
        except FileNotFoundError:
            pass
    speech = "The nervous system has been reset. All counters back to zero. Ready for new impulses."
    return alexa_response(speech,
                         card_title="Reset",
                         card_text="Event count reset to zero")


def handle_help():
    speech = (
        "Building ops can tell you about the demo's nervous system. "
        "Try: status report, how many devices, what's the event rate, "
        "initiate lockdown, or reset the count."
    )
    return alexa_response(speech, should_end=False,
                         card_title="Help",
                         card_text="Commands: status, devices, rate, lockdown, reset")
