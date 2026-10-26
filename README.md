# Connected Ops Lab
Telemetry emulator → FastAPI ingestion → dashboard with validation, risk scoring, and basic business impact.
Personal model of a connected-ops loop. Simulated data, in-memory, single unit.
## Run locally
```bash
docker-compose up –build
```
- API: http://localhost:8000
- Dashboard: http://localhost:8501
## What it shows
- Telemetry stream that drifts over time
- Validation of incoming signals
- Simple risk band
- Basic view of operational impact
- Button to simulate an anomaly
## Notes
This is a personal demo. It is not production software and does not use real fleet data.
## Architecture
Telemetry Emulator → FastAPI Ingestion → Streamlit Dashboard
## Example payload
```json
{
“ts”: “2025-01-01T12:34:56.789Z”,
“vehicle_id”: “unit_42”,
“coolant_temp_f”: 195.0,
“intake_air_temp_f”: 70.0,
“engine_rpm”: 2100,
“speed_mph”: 65.0,
“vibration_score”: 1.2,
“engine_hours”: 123.45
}
```
