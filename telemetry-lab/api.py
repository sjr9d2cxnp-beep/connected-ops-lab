# telemetry-lab/api.py

from typing import List, Dict
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Connected Ops Telemetry API")

# In-memory store for recent telemetry points
DATA: List[Dict] = []


class Telemetry(BaseModel):
    ts: str
    vehicle_id: str
    coolant_temp_f: float
    intake_air_temp_f: float
    engine_rpm: int
    speed_mph: float
    vibration_score: float
    engine_hours: float


@app.post("/telemetry")
def ingest(point: Telemetry):
    """
    Ingest a single telemetry sample from the emulator.
    """
    DATA.append(point.dict())

    # keep only the latest ~3000 samples
    if len(DATA) > 3000:
        DATA.pop(0)

    return {"status": "ok", "count": len(DATA)}


@app.get("/telemetry")
def read_recent(limit: int = 600):
    """
    Return the most recent telemetry samples (default 600).
    Dashboard reads from here.
    """
    if limit <= 0:
        return []

    # Return the last N samples in chronological order
    subset = DATA[-limit:]
    return subset
