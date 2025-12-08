# Predictive Maintenance Dashboard — Connected Ops Lab Module

> **Part of the Connected Ops Lab.  
For architecture & deployment instructions, see the root README.**

---

## 🧭 Overview

This dashboard consumes real-time telemetry and turns it into maintenance insights:

- Health scoring (Low / Medium / High)
- Anomaly detection (temp spikes, intake drift, vibration rise)
- Rolling trend analysis
- Prioritized maintenance list
- Per-unit deep dive

All logic is transparent and explainable (no black-box ML).

---

## 📊 What It Shows

### Fleet Summary
- Units monitored  
- High-risk and medium-risk counts  
- Automatically refreshed view  

### Prioritized Maintenance List
A sortable list of assets ranked by risk and contributing metrics.

### Unit Detail View
- Latest telemetry  
- Trend lines with smoothing  
- Rolling averages  
- Vibration profile  
- Engine behavior  

---

## 🧠 Scoring Logic

Risk score is calculated from:

- Hard thresholds:  
  - Coolant > 240°F  
  - Intake > 180°F  
  - Vibration > 1.5  

- Rolling trend deviations  
- Cumulative anomaly weight

Scores convert to bands:

- **6+** → High  
- **3–5** → Medium  
- **0–2** → Low  

---

## 🚀 Running the Dashboard

This module runs automatically inside Docker as the `dashboard` service.

Visit:

http://localhost:8501
after running docker-compose up --build


---

## 📁 Files

- **app.py** — Main dashboard  
- **requirements.txt** — Streamlit dependencies  
- **Dockerfile** — Runtime environment  

---

## 🧩 How This Fits the Lab

The dashboard is the final presentation layer that demonstrates how a Sales Engineer would translate noisy sensor data into:

- operational clarity  
- maintenance priorities  
- insights a customer can act on  

