# Ansible Automation Platform / Event-Driven Ansible Integration

## Overview

Event-Driven Ansible (EDA) sits between the north platform layer and enterprise systems (further north). It listens to the event stream, matches conditions via rulebooks, and triggers playbooks that act on infrastructure, SAP, and enterprise systems.

This is a validated Red Hat enterprise automation stack: **Red Hat OpenShift + Event-Driven Ansible + Ansible Automation Platform**.

---

## Architecture Position

```
South (edge devices / simulations)
    ↓ CloudEvents → /ingest
North (OpenShift — aggregation, routing, Redis)
    ↓ webhook or Redis pub/sub → EDA rulebook engine
Event-Driven Ansible (AAP)
    ↓ rulebook matches event condition → triggers playbook
Ansible Playbook (actuator)
    ↓
Further North (SAP BTP, SAP ERP, ServiceNow, CMDB, field systems)
```

EDA connects to north via:
- **Webhook source plugin** — north-api POSTs matched events to EDA webhook endpoint
- **Redis source plugin** — EDA subscribes directly to Redis pub/sub channel (`ohc:events`)

No changes required to south or north for new EDA rules — rulebooks are additive.

---

## Use Cases

### UC-1: GRC Kill Chain — Automated Threat Response

**Trigger event:** `eventclass: incident` — SSH brute force, rogue device, or badge anomaly detected

**EDA Rulebook:**
```yaml
- name: GRC kill chain response
  hosts: all
  sources:
    - ansible.eda.webhook:
        host: 0.0.0.0
        port: 5001
  rules:
    - name: Block brute force source
      condition: event.eventclass == "incident" and event.data.threat == "ssh_brute_force"
      action:
        run_playbook:
          name: block_ip_and_notify.yml
```

**Playbook actions:**
- Block source IP on perimeter firewall (via API or SSH)
- Open ServiceNow P2 incident ticket
- Notify SOC via webhook (Slack, Teams, PagerDuty)
- Log to SIEM (Splunk, QRadar)
- Update CMDB asset status

**Demo value:** Shows OHC + AAP as a closed-loop security response system. Human sees the event hit the dashboard and the ticket appear in ServiceNow — no human in the loop.

---

### UC-2: HVAC Threshold — Automated Building System Override

**Trigger event:** `eventclass: building` — zone temperature exceeds threshold (e.g., Zone 4 at 81°F, threshold 78°F)

**EDA Rulebook:**
```yaml
rules:
  - name: Force cooling override
    condition: event.eventclass == "building" and event.data.status == "THRESHOLD_EXCEEDED"
    action:
      run_playbook:
        name: hvac_override.yml
```

**Playbook actions:**
- Call JCI OpenBlue / Metasys API to force cooling override on affected zone
- Log override event back to north (/ingest) for audit trail
- Create SAP PM work order for HVAC inspection
- Notify facilities management

**Demo value:** Physical building system responds to a CloudEvent automatically. Closes the loop between sensor → platform → action without a human clicking anything.

---

### UC-3: Shop Floor Defect — SAP QM Notification and Quarantine

**Trigger event:** `eventclass: sensor` — production defect detected at quality inspection station

**EDA Rulebook:**
```yaml
rules:
  - name: QM defect response
    condition: event.eventclass == "sensor" and event.data.result == "DEFECT_DETECTED"
    action:
      run_playbook:
        name: sap_qm_notification.yml
```

**Playbook actions:**
- Create SAP QM notification via RFC/BAPI or SAP BTP API
- Quarantine production order (set system status QMLOCK)
- Notify line supervisor via SAP workflow
- Update MII dashboard with defect count
- Trigger containment sampling playbook if defect rate exceeds threshold

**Demo value:** SAP QM integration via Ansible — no custom middleware required. Shows AAP as the integration layer between OHC events and SAP ERP.

---

### UC-4: Mercedes Vehicle Fault — SAP PM Work Order Dispatch

**Trigger event:** `eventclass: telem` — vehicle fault code or critical sensor reading from Mercedes/Smartcar relay

**EDA Rulebook:**
```yaml
rules:
  - name: Vehicle fault work order
    condition: event.eventclass == "telem" and event.data.severity == "critical"
    action:
      run_playbook:
        name: sap_pm_work_order.yml
```

**Playbook actions:**
- Create SAP PM work order (maintenance notification) via RFC or BTP
- Assign to nearest qualified technician based on geolocation data in event payload
- Send field dispatch notification (SMS, Teams)
- Update fleet management system with vehicle status
- Schedule follow-up inspection work order

**Demo value:** Connected vehicle → CloudEvent → automated field dispatch. Real-time edge data driving SAP PM without manual data entry.

---

### UC-5: UPS Battery Critical — ITSM Ticket and On-Call Page

**Trigger event:** `eventclass: telem` — UPS battery health below replacement threshold or runtime critically low

**EDA Rulebook:**
```yaml
rules:
  - name: UPS critical response
    condition: event.eventclass == "telem" and event.data.batteryHealth < 60
    action:
      run_playbook:
        name: ups_critical_response.yml
```

**Playbook actions:**
- Open P1 ITSM ticket (ServiceNow, Jira Service Management)
- Page on-call infrastructure engineer (PagerDuty)
- Check downstream systems dependent on this UPS (CMDB lookup)
- Notify data center facilities team
- If runtime < 15 min: trigger graceful shutdown sequence for non-critical systems

**Demo value:** Preventive automation before an outage. Shows EDA acting on telemetry thresholds — not just alerts after the fact.

---

## Generic Extension Pattern

Any new event source (south component) automatically becomes an EDA trigger candidate:

1. South emits CloudEvent with `eventclass` and structured `data` payload
2. North ingests and publishes to Redis (`ohc:events` channel)
3. EDA Redis source plugin picks up event
4. Rulebook matches on `eventclass`, `type`, or any `data` field
5. Playbook executes against any target: SAP, ITSM, infrastructure, notifications

**No changes to south or north required.** New automation is purely additive — new rulebook + new playbook.

### EDA Connection to North

```bash
# Redis source plugin config (in EDA rulebook)
sources:
  - ansible.eda.redis:
      host: redis.qr-demo-qa.svc.cluster.local
      port: 6379
      channels:
        - ohc:events
```

Or via webhook if north-api POSTs selectively filtered events:

```bash
# north-api posts to EDA webhook for high-severity events
EDA_WEBHOOK_URL = os.environ.get("EDA_WEBHOOK_URL", "")
if event.get("eventclass") in ["incident", "alert"] and EDA_WEBHOOK_URL:
    requests.post(EDA_WEBHOOK_URL, json=event)
```

---

## Open Items

- [ ] Provision AAP / EDA instance (RHDP catalog or shared cluster)
- [ ] Implement Redis source plugin connection from EDA to north Redis
- [ ] Build demo rulebook for UC-1 (GRC kill chain) as first working example
- [ ] Stub ServiceNow sandbox for ticket creation demo
- [ ] Add EDA layer to architecture diagram on GitHub Pages

---

**Established:** 2026-02-21
**Author:** Jim O'Donnell + Chloe
**Related:** NORTH-SOUTH-PRINCIPLE.md, REBUILD-PLAN.md
