# Connected Ops Lab  
### Real-Time Telemetry → FastAPI Ingestion → Predictive Maintenance Dashboard  
*A containerized, end-to-end demo showing how a Sales Engineer turns raw machine data into operational clarity.*

---

## 🚀 Overview

**Connected Ops Lab** is a lightweight but realistic IoT/telematics workflow that demonstrates how modern fleet and equipment operations transform raw telemetry into actionable decisions.

It simulates the core loop used across platforms like Samsara, Motive, Netradyne, and OEM diagnostic stacks:

**Telemetry → Validation → Signal → Risk → Insight → Business Value**

The lab consists of four components:

---

### 1. Telemetry Emulator (OBD-II Style)  

A Python process that streams realistic engine and sensor signals every second:

- RPM  
- Coolant temperature  
- Intake air temperature  
- Speed  
- Vibration score  
- Engine hours (with natural drift)

The emulator loads a **seed profile** from `telemetry_emulator.json` and evolves it over time, creating believable operational behavior.

---

### 2. FastAPI Ingestion Service  

A lightweight ingestion layer that:

- Receives streaming telemetry via `POST /telemetry`  
- Stores a rolling window of recent samples in memory  
- Exposes the stream for dashboards at `GET /telemetry`  
- Supports **push-button anomaly simulation** via `POST /simulate_anomaly`

This reflects how real IoT gateways and cloud ingestion services collect and route machine signals.

---

### 3. Predictive Maintenance Dashboard (Streamlit — `app.py`)  

A production-style SE demo that includes:

- **Validation Layer** – flags malformed or out-of-range signals  
- **Health & Risk Scoring** – converts telemetry into a risk band  
- **Business Value Panel** – estimates downtime exposure and cost impact  
- **Demo Controls** – simulate coolant overheat, vibration spikes, or speed anomalies  
- **Fleet & Per-Unit Views** – drill into operational context  

The dashboard auto-refreshes every few seconds so charts and metrics move continuously in the background, giving a “live control room” feel.

---

### 4. MVP Debug Dashboard (`dashboard.py`)  

A slim, fast-loading viewer for development and quick inspection.

---

## 🧠 What This Demonstrates (Sales Engineering POV)

This project is intentionally built to reflect real pre-sales workflows:

- **Data realism** – telemetry is noisy and drifts over time.  
- **Validation as a first-class concept** – data quality is visible and explainable.  
- **Repeatable demo scenarios** – `/simulate_anomaly` provides predictable spikes.  
- **Clear business value** – the Business Impact panel ties engineering risk → downtime → dollar impact.  
- **Realistic operational narrative** – mirrors how connected-operations tools surface value in fleet, heavy equipment, and manufacturing environments.

---

## 🧱 Architecture

```text
+--------------------------+       +-----------------------------+       +-------------------------------+
|  Telemetry Emulator      | ----> |  FastAPI Ingestion Service | ----> |  Streamlit Dashboards         |
|  (emulator.py)           | POST  |  /telemetry, /simulate_*   | GET   |  app.py / dashboard.py        |
+--------------------------+       +-----------------------------+       +-------------------------------+
            ^                                                                   |
            |                                                                   |
            +---------------- Seed Profile (telemetry_emulator.json) -----------+

---
## 📡 Example Telemetry Payload (What the API Expects)

Every second, the emulator sends a JSON payload like this to `POST /telemetry`:

```jsonA
{
  "ts": "2025-01-01T12:34:56.789Z",
  "vehicle_id": "corolla_2019",
  "coolant_temp_f": 195.0,
  "intake_air_temp_f": 70.0,
  "engine_rpm": 2100,
  "speed_mph": 65.0,
  "vibration_score": 1.2,
  "engine_hours": 123.45
}

---
