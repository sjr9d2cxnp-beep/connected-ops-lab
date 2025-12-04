# api.py
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List

app = FastAPI()

DATA: List[dict] = []

class Telemetry(BaseModel):
    ts: str
    vehicle_id: str
    rpm: int
    coolant_temp_c: int
    speed_mph: int

@app.post("/telemetry")
def ingest(point: Telemetry):
    DATA.append(point.dict())
    if len(DATA) > 300:
        DATA.pop(0)
    return {"status": "ok", "count": len(DATA)}

@app.get("/telemetry")
def read_latest():
    return DATA[-300:]