"""
Connected Ops Lab - Telemetry API

FastAPI service that:
- Accepts POSTed telemetry from the emulator at /telemetry
- Exposes recent telemetry via GET /telemetry
- Lets the dashboard inject demo anomalies via POST /simulate_anomaly
- Tracks anomaly counts by type and exposes them via GET /anomaly_stats

This gives the dashboard enough context to tell a "cost of early
detection vs ignored failure" story.
"""

from collections import deque
from datetime import datetime, timezone
from typing import Deque, Dict, List, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Connected Ops Lab API")

# -------------------------------------------------------------------
# Data models
# -------------------------------------------------------------------


class TelemetryIn(BaseModel):
    ts: datetime = Field(..., description="Timestamp in ISO format (UTC)")
    vehicle_id: str = Field(..., description="Vehicle identifier")
    coolant_temp_f: float
    intake_air_temp_f: float
    engine_rpm: float
    speed_mph: float
    vibration_score: float
    engine_hours: float


class TelemetryOut(TelemetryIn):
    pass


class SimulateAnomalyRequest(BaseModel):
    anomaly_type: Literal["coolant_overheat", "vibration_spike", "speed_anomaly"]


class AnomalyStats(BaseModel):
    coolant_overheat: int
    vibration_spike: int
    speed_anomaly: int


# -------------------------------------------------------------------
# In-memory storage
# -------------------------------------------------------------------

BUFFER_SIZE = 2000
TELEMETRY_BUFFER: Deque[Dict] = deque(maxlen=BUFFER_SIZE)

ANOMALY_COUNTS: Dict[str, int] = {
    "coolant_overheat": 0,
    "vibration_spike": 0,
    "speed_anomaly": 0,
}


# -------------------------------------------------------------------
# Helper functions
# -------------------------------------------------------------------


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _append_telemetry(payload: Dict) -> None:
    TELEMETRY_BUFFER.append(payload)


# -------------------------------------------------------------------
# Telemetry endpoints
# -------------------------------------------------------------------


@app.post("/telemetry", response_model=Dict[str, str])
def ingest_telemetry(body: TelemetryIn):
    payload = body.dict()
    _append_telemetry(payload)
    return {"status": "ok"}


@app.get("/telemetry", response_model=List[TelemetryOut])
def get_telemetry(limit: int = 600):
    if limit <= 0:
        raise HTTPException(status_code=400, detail="limit must be > 0")
    # return latest N samples
    items = list(TELEMETRY_BUFFER)[-limit:]
    return items


# -------------------------------------------------------------------
# Anomaly simulation / stats
# -------------------------------------------------------------------


@app.post("/simulate_anomaly", response_model=Dict[str, str])
def simulate_anomaly(req: SimulateAnomalyRequest):
    """
    Inject a single anomalous telemetry sample based on the latest
    known sample, and increment the anomaly counters.

    This is designed for SE demos: each button press corresponds to
    a realistic early-warning event.
    """
    if not TELEMETRY_BUFFER:
        raise HTTPException(
            status_code=400,
            detail="No baseline telemetry available to mutate; start emulator first.",
        )

    base = TELEMETRY_BUFFER[-1].copy()

    # update timestamp so it appears as a fresh event
    base["ts"] = _now_utc().isoformat()

    anomaly_type = req.anomaly_type

    if anomaly_type == "coolant_overheat":
        # Simulate overheating coolant + a bit more vibration
        base["coolant_temp_f"] = max(base["coolant_temp_f"], 250.0)
        base["vibration_score"] = float(base["vibration_score"]) + 0.2

    elif anomaly_type == "vibration_spike":
        # Simulate a sharp vibration spike (e.g., early bearing/suspension issue)
        base["vibration_score"] = max(float(base["vibration_score"]) + 2.0, 3.5)

    elif anomaly_type == "speed_anomaly":
        # Simulate sustained speeding (e.g., driver going > 80 mph)
        base["speed_mph"] = max(base["speed_mph"], 83.0)
        base["engine_rpm"] = max(base["engine_rpm"], 3200.0)

    else:
        raise HTTPException(status_code=400, detail=f"Unknown anomaly {anomaly_type}")

    # Append anomalous sample & track stats
    _append_telemetry(base)
    ANOMALY_COUNTS[anomaly_type] = ANOMALY_COUNTS.get(anomaly_type, 0) + 1

    return {"status": "ok"}


@app.get("/anomaly_stats", response_model=AnomalyStats)
def get_anomaly_stats():
    """
    Return counts of each anomaly type since process start. For demo
    purposes, this is enough to illustrate cumulative business impact.
    """
    return AnomalyStats(**ANOMALY_COUNTS)
