# telemetry-lab/emulator.py

import os
import time
import random
import requests
from datetime import datetime, timezone

# Inside the API container, the API is on localhost.
# You can override via API_URL env if you ever change layout.
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000/telemetry")
VEHICLE_ID = os.getenv("VEHICLE_ID", "corolla_2019")

# simple in-memory counter for engine hours
engine_hours = 0.0


def generate_point() -> dict:
    """
    Generate a single telemetry sample for a cruising Corolla.
    """
    global engine_hours

    # --- CRUISE BEHAVIOR ---
    # Target: ~70 mph cruise, rpm 1800–2100

    rpm = int(random.normalvariate(1950, 80))
    rpm = max(1800, min(2100, rpm))

    speed = 70 + random.normalvariate(0, 2.0)
    speed = max(60, min(80, speed))

    # Coolant: normal ~195°F with slight noise
    coolant = 195 + random.normalvariate(0, 2.0)

    # Intake air: base ~65°F, rises slightly with rpm load
    intake = 65 + (rpm - 1950) / 80.0 + random.normalvariate(0, 1.0)

    # --- ANOMALY INJECTION (OVERHEAT) ---
    # Small chance each sample to simulate a developing coolant issue
    overheat = random.random() < 0.03
    if overheat:
        # Spike coolant temp into a clearly bad range
        coolant = random.uniform(225, 235)
        # Intake air typically hotter when engine is struggling
        intake += random.uniform(8, 15)

    # --- VIBRATION MODEL ---
    # Base vibration around 0.3, nudged by rpm and especially overheat
    vib_base = 0.3 + max(0.0, (rpm - 2000) / 500.0)
    vibration = vib_base + max(0.0, (coolant - 210) / 40.0) + abs(
        random.normalvariate(0, 0.05)
    )

    # --- ENGINE HOURS ---
    engine_hours += 1.0 / 3600.0

    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "vehicle_id": VEHICLE_ID,
        "coolant_temp_f": round(coolant, 1),
        "intake_air_temp_f": round(intake, 1),
        "engine_rpm": rpm,
        "speed_mph": round(speed, 1),
        "vibration_score": round(vibration, 2),
        "engine_hours": round(engine_hours, 2),
    }


def main():
    print(f"[emulator] Sending telemetry to {API_URL} as {VEHICLE_ID}", flush=True)
    while True:
        point = generate_point()
        try:
            r = requests.post(API_URL, json=point, timeout=2)
            print("[emulator] sent", r.status_code, point, flush=True)
        except Exception as e:
            print("[emulator] error sending:", e, flush=True)
        time.sleep(1)


if __name__ == "__main__":
    main()
