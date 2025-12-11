# emulator/emulator.py
#
# Connected Ops Lab – Telemetry Emulator
#
# Generates Corolla-like cruise telemetry and streams it into the FastAPI
# ingestion service. Parameters are coupled so that RPM and speed influence
# intake air temp, coolant temp, and vibration.

import json
import os
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

import requests

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000/telemetry")
VEHICLE_ID = os.getenv("VEHICLE_ID", "corolla_2019")
BASE_PAYLOAD_PATH = os.getenv(
    "BASE_PAYLOAD_PATH",
    str(Path(__file__).parent / "telemetry_emulator.json"),
)


@dataclass
class TelemetryState:
    """
    Simple stateful emulator roughly modeling a Corolla at highway cruise.

    Target "healthy" ranges:
      - engine_rpm:       ~2200–2700
      - speed_mph:        ~68–72
      - coolant_temp_f:   ~185–200
      - intake_air_temp:  ~65–75
      - vibration_score:  low (<1.5)
    """

    coolant_temp_f: float
    intake_air_temp_f: float
    engine_rpm: float
    speed_mph: float
    vibration_score: float
    engine_hours: float = 0.0

    # cruise setpoints
    RPM_SETPOINT: float = 2400.0
    SPEED_SETPOINT: float = 70.0
    COOLANT_BASE: float = 190.0
    INTAKE_BASE: float = 70.0

    @classmethod
    def from_file(cls, path: str) -> "TelemetryState":
        """Initialize from a JSON seed file."""
        with open(path, "r") as f:
            seed = json.load(f)
        return cls(
            coolant_temp_f=seed.get("coolant_temp_f", 190.0),
            intake_air_temp_f=seed.get("intake_air_temp_f", 70.0),
            engine_rpm=seed.get("engine_rpm", 2400.0),
            speed_mph=seed.get("speed_mph", 70.0),
            vibration_score=seed.get("vibration_score", 0.8),
            engine_hours=seed.get("engine_hours", 0.0),
        )

    def _approach(self, value: float, target: float, gain: float) -> float:
        """
        Move value slightly toward target (1st-order lag) with some noise.
        """
        delta = target - value
        return value + gain * delta

    def step(self, dt_seconds: float = 1.0) -> None:
        """
        Advance the emulator one time step with coupled dynamics.

        - RPM and speed drift mildly around their setpoints.
        - Coolant & intake temps are influenced by RPM and speed.
        - Vibration increases with RPM and deviation from ideal speed.
        - Engine hours accumulate over time.
        """

        # accumulate engine hours
        self.engine_hours += dt_seconds / 3600.0

        # --- RPM & Speed: gently track setpoints with noise ---
        # treat them as "cruise control" with a bit of variation
        rpm_noise = random.uniform(-80.0, 80.0)
        spd_noise = random.uniform(-1.5, 1.5)

        self.engine_rpm = self._approach(self.engine_rpm, self.RPM_SETPOINT, 0.05)
        self.engine_rpm += rpm_noise
        self.engine_rpm = max(1500.0, min(self.engine_rpm, 3200.0))

        self.speed_mph = self._approach(self.speed_mph, self.SPEED_SETPOINT, 0.08)
        self.speed_mph += spd_noise
        self.speed_mph = max(45.0, min(self.speed_mph, 80.0))

        # --- Intake air temp: base + small effect from RPM & speed ---
        # Higher RPM and speed slightly warm the intake path.
        intake_effect = 0.002 * (self.engine_rpm - self.RPM_SETPOINT) + 0.03 * (
            self.speed_mph - self.SPEED_SETPOINT
        )
        self.intake_air_temp_f = self._approach(
            self.intake_air_temp_f, self.INTAKE_BASE + intake_effect, 0.15
        )
        self.intake_air_temp_f += random.uniform(-0.3, 0.3)
        self.intake_air_temp_f = max(60.0, min(self.intake_air_temp_f, 80.0))

        # --- Coolant temp: base + effect from RPM + slow upward drift with hours ---
        load_effect = 0.004 * (self.engine_rpm - self.RPM_SETPOINT)
        hours_effect = 0.01 * self.engine_hours  # very slow trend up as engine runs
        coolant_target = self.COOLANT_BASE + load_effect + hours_effect
        self.coolant_temp_f = self._approach(self.coolant_temp_f, coolant_target, 0.08)
        self.coolant_temp_f += random.uniform(-0.4, 0.4)
        self.coolant_temp_f = max(180.0, min(self.coolant_temp_f, 210.0))

        # --- Vibration: increases with RPM and deviation from ideal speed ---
        rpm_component = max(0.0, (self.engine_rpm - 2200.0) / 1500.0)
        speed_component = abs(self.speed_mph - 70.0) / 20.0
        base_vib = 0.5 + 0.6 * rpm_component + 0.6 * speed_component
        self.vibration_score = base_vib + random.uniform(-0.1, 0.1)
        self.vibration_score = max(0.2, min(self.vibration_score, 3.0))

    def to_payload(self) -> Dict:
        """Convert current state into a JSON-serializable payload."""
        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "vehicle_id": VEHICLE_ID,
            "coolant_temp_f": float(self.coolant_temp_f),
            "intake_air_temp_f": float(self.intake_air_temp_f),
            "engine_rpm": float(self.engine_rpm),
            "speed_mph": float(self.speed_mph),
            "vibration_score": float(self.vibration_score),
            "engine_hours": float(self.engine_hours),
        }


def main() -> None:
    state = TelemetryState.from_file(BASE_PAYLOAD_PATH)
    print(f"[emulator] Sending telemetry to {API_URL} as {VEHICLE_ID}", flush=True)

    while True:
        state.step(dt_seconds=1.0)
        payload = state.to_payload()
        try:
            r = requests.post(API_URL, json=payload, timeout=2)
            print("[emulator]", r.status_code, payload, flush=True)
        except Exception as exc:
            print("[emulator] error sending:", exc, flush=True)
        time.sleep(1)


if __name__ == "__main__":
    main()
