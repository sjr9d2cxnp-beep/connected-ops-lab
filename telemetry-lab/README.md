# Telemetry Emulator — Connected Ops Lab Module

> **Part of the Connected Ops Lab.  
For system architecture & deployment, see the root README.**

---

## 🎯 Purpose

This module simulates a real OBD-II / IoT telematics device streaming live vehicle data into a FastAPI endpoint.  
It powers the Predictive Maintenance Dashboard by producing clean, realistic, structured telemetry.

---

## 🔧 What It Generates (Fahrenheit-based)

- RPM (1800–2100 cruising)
- Coolant temp °F (~195°F normal behavior)
- Intake air temp °F (60–75°F depending on load)
- Speed (mph)
- Vibration score
- Engine hours

Includes:
- natural noise  
- slow thermal drift  
- anomaly spikes (overheat, vibration rise, etc)

---

## 📡 API Overview

### Endpoint: `POST /telemetry`
Accepts telemetry packets from the emulator.

### Endpoint: `GET /telemetry`
Returns a recent sliding window of recorded telemetry.

---

## 📁 File Overview

- **emulator.py** — Generates synthetic telemetry and POSTs it continuously.  
- **api.py** — FastAPI application that ingests and exposes telemetry.  
- **telemetry_emulator.json** — Starting baseline values used by the emulator.  
- **Dockerfile** — Runs emulator + FastAPI in the same container.

---

## 🏃 How It Runs

You don't run this module manually.  
Docker Compose starts it automatically as the `api` service.

See root README for full instructions.
