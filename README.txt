This is a lightweight telematics pipeline MVP that simulates
vehicle telemetry, ingests it through a REST API,
and visualizes it through a dashboard.

This is intended to mirror how connected-operations
platforms (Samsara/Motive/Fleetio-adjacent) work
in real life:

Device/sensor -> API ingestion -> cloud/logic
-> dashboard

Demonstrating ability to:

-model telemetry
-build REST endpoints for ingestion
-validate and store time-series data
-visualize trends for non-technical users
-explain a technical system clearly

What's in the repo

-api.py (FastAPI app)
-emulator.py (telemetry generator)
-dashboard.py (Streamlit UI)
-JSON file (sample output)
-requirements.txt
-README.txt

Prerequisites
-Python 3.10 installed
-Terminal Access (Powershell/CMD)

 Clone the repository
bash
git clone https://github.com/sjr9d2cxnp-beep/obd-telemetry-emulator.git
cd obd-telemetry-emulator

-Create virtual environment
    In terminal:
    python -m venv venv

-Activate venv
    Terminal: 
    venv\Scripts\Activate.ps1

If it is blocked, run this ONCE as an admin in Powershell:

Set-ExecutionPolicy -ExecutionPolicyRemoteSigned -Scope CurrentUser

Activate again.

Install dependencies:

pip install -r requirements.txt


You need 3 terminal windows to run this:

Terminal 1: Start api -> uvicorn api:app -reload
Terminal 2: Run emulator -> python emulator.py
Terminal 3: Run the dashboard -> streamlit run dashboard.py

Verify its working by opening http://127.0.0.1:8000/telemetry
You should see a growing list of JSON telemetry points.

Dashboard should show latest row + RPM line graph

Data is random demo data, so the RPM and corresponding graphs
will look chaotic. 

Next version will use realistic driving modes.


PLANNED:
-GitHub repo and Loom demo walkthrough
-Dashboard panels (Alerts, system status, etc)
-Alert Logic (overheat, high rpm, etc)
-Improve emulator behavior (smooth idle, city -> hwy transitions)
