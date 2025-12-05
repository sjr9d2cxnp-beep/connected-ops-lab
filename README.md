# Connected Ops Lab  
### Real-Time Telemetry → FastAPI Ingestion → Predictive Maintenance Dashboard  
*A fully containerized proof-of-concept demonstrating how a Sales Engineer turns machine data into operational clarity.*

---

## 🚀 Overview

Connected Ops Lab is a small, end-to-end IoT/telematics system:

1. **Telemetry Emulator (OBD-II style)**  
   Generates realistic vehicle signals (RPM, coolant temp, intake temp, vibration, engine hours).

2. **FastAPI Ingestion Service**  
   Receives streaming telemetry at `/telemetry`, stores recent history, and exposes it for the dashboard.

3. **Predictive Maintenance Dashboard (Streamlit)**  
   Scores assets on maintenance risk, highlights anomalies, and displays intuitive trend visualizations.

All components run together with a single command via Docker Compose.

This setup mirrors real Connected Operations platforms (Samsara, Geotab, OEM telematics), but in a recruiter-friendly, self-contained demo.


---

## 🧩 Architecture

connected-ops-lab/
│
├── telemetry-emulator/              # Synthetic OBD-II signal generator + API
│   ├── emulator.py                  # Produces streaming RPM/temp/vibration/etc.
│   ├── telemetry_emulator.json      # Signal configuration + drift patterns
│   ├── api.py                       # FastAPI service exposing /telemetry endpoint
│   ├── requirements.txt
│   └── Dockerfile
│
├── predictive-maint-dash/           # Streamlit dashboard for asset insights
│   ├── app.py                       # Visualization + anomaly scoring
│   ├── requirements.txt
│   └── Dockerfile
│
├── docker-compose.yml               # Orchestrates both services with one command
└── README.md                        # You're reading it

---

## 📦 What This Lab Demonstrates

### **1. Streaming Telemetry (OBD-II style)**  
- RPM (± 1800–2100 during cruise)  
- Coolant temp around 195°F with noise and drift  
- Intake air temperature tied to load  
- Vibration score  
- Engine hours  

Includes:  
- realistic cruising behavior  
- anomaly patterns (thermal spikes, creeping vibration trends)

---

### **2. Real-Time Data Pipeline**
The emulator pushes JSON packets to FastAPI → FastAPI serves them to the dashboard.

This shows your ability to:
- structure time-series signals  
- design APIs  
- handle ingestion and refresh  
- link multiple services into a coherent flow  

---

### **3. Predictive Maintenance Logic**
The dashboard calculates:
- risk bands (Low / Medium / High)  
- rule-based thresholds (coolant, intake air, vibration)  
- trend-based rolling windows  
- prioritized maintenance list  

It visually explains:  
> “Here’s why this unit is at risk — and what signal caused it.”

This is exactly how a Sales Engineer walks a customer through proof-of-value.

---

## 🛠️ How to Run (One Command)

Make sure Docker Desktop is running.

From the repo root:

```sh
docker-compose up --build
```

Then visit:

Dashboard: http://localhost:8501

API Stream: http://localhost:8000/telemetry

To stop everything:
CTRL + C
docker-compose down
