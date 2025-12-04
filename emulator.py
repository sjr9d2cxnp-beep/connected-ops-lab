import time
import random
from datetime import datetime, timezone

import requests

API_URL = "http://127.0.0.1:8000/telemetry"
VEHICLE_ID = "corolla_2019"


def telemetry_stream():
    """
    Generate a continuous stream of Corolla telemetry in °F / mph.

    Normal behavior:
      - Coolant ~190–210°F with small drift
      - Intake air ~80–110°F
      - RPM ~1700–2300
      - Speed ~50–70 mph
      - Vibration_score ~0.3–0.6

    Occasionally we simulate a developing fault:
      - Coolant gradually creeps up
      - Vibration increases
    """
    coolant = 195.0
    intake = 90.0
    rpm = 1800.0
    speed = 60.0
    vibration = 0.35
    engine_hours = 0.0

    fault_active = False
    fault_seconds_left = 0

    while True:
        # ----- base random walk for normal cruising -----
        coolant += random.uniform(-0.4, 0.7)
        intake += random.uniform(-0.3, 0.5)
        rpm += random.uniform(-80, 80)
        speed += random.uniform(-3, 3)
        vibration += random.uniform(-0.02, 0.02)

        # clamp to sane ranges
        coolant = max(180.0, min(coolant, 230.0))
        intake = max(70.0, min(intake, 140.0))
        rpm = max(700.0, min(rpm, 2800.0))
        speed = max(0.0, min(speed, 80.0))
        vibration = max(0.2, min(vibration, 1.2))

        # ----- anomaly simulation (coolant + vibration fault) -----
        if not fault_active and random.random() < 0.02:
            # 2% chance each second to start a fault episode
            fault_active = True
            fault_seconds_left = random.randint(45, 120)

        if fault_active:
            # slow creep upwards, capped so it doesn't look insane
            coolant += random.uniform(0.5, 1.5)
            vibration += random.uniform(0.05, 0.12)

            coolant = min(coolant, 250.0)
            vibration = min(vibration, 2.5)

            fault_seconds_left -= 1
            if fault_seconds_left <= 0:
                fault_active = False

        # ----- engine hours progression -----
        engine_hours += 1.0 / 3600.0  # +1 second

        point = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "vehicle_id": VEHICLE_ID,
            "coolant_temp_f": round(coolant, 1),
            "intake_air_temp_f": round(intake, 1),
            "engine_rpm": int(rpm),
            "speed_mph": round(speed, 1),
            "vibration_score": round(vibration, 3),
            "engine_hours": round(engine_hours, 2),
        }

        yield point
        time.sleep(1)


def main():
    for point in telemetry_stream():
        try:
            r = requests.post(API_URL, json=point, timeout=2)
            print("sent", r.status_code, point)
        except Exception as e:
            print("error sending:", e)
            # give the API a moment to come back
            time.sleep(3)


if __name__ == "__main__":
    main()
