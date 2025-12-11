# dashboard/app.py
#
# Connected Ops Lab – Predictive Maintenance Dashboard
#
# Streamlit UI that:
#   - Pulls recent telemetry from the FastAPI service
#   - Applies a validation layer to mimic real-world data quality issues
#   - Derives risk scores and bands from raw signals
#   - Adjusts risk based on coolant + vibration spike patterns *only
#     within the active demo scenario window*
#   - Exposes a business impact panel with early vs deferred costs
#   - Offers push-button anomaly simulations (coolant, vibration, speed)
#   - Auto-refreshes so updates appear live without manual reloads

import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# -------------------------------------------------
# Config
# -------------------------------------------------

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000/telemetry")
BASE_API_PREFIX = API_URL.rsplit("/telemetry", 1)[0]
SIM_URL = os.getenv("SIM_API_URL", f"{BASE_API_PREFIX}/simulate_anomaly")

PAGE_TITLE = "Connected Ops Lab – Predictive Maintenance"

REFRESH_SECONDS = 2  # dashboard auto-refresh
ANOMALY_WINDOW_SECONDS = int(os.getenv("ANOMALY_WINDOW_SECONDS", "60"))

RISK_BINS = [-1, 30, 65, 999]
RISK_LABELS = ["Low", "Medium", "High"]

# Pattern analysis windows (relative to scenario start)
COOLANT_PATTERN_WINDOW_SECONDS = 90
VIBRATION_PATTERN_WINDOW_SECONDS = 180

# Thresholds for what counts as a "spike"
COOLANT_SPIKE_THRESHOLD_F = 230.0
VIBRATION_SPIKE_THRESHOLD = 2.8

# Business modeling assumptions (food-service delivery vehicle)
VEHICLE_REVENUE_PER_HOUR = 200.0  # lost revenue if truck is down
LABOR_RATE_PER_HOUR = 150.0       # tech + diagnostic

# Coolant – early pump/thermostat vs ignored until failure
COOLANT_EARLY_REPAIR = 1200.0
COOLANT_EARLY_DOWNTIME_HOURS = 4.0
COOLANT_DEFER_REPAIR = 3500.0
COOLANT_DEFER_DOWNTIME_HOURS = 12.0

# Vibration – early bearing/bushing vs major failure
VIB_EARLY_REPAIR = 900.0
VIB_EARLY_DOWNTIME_HOURS = 3.0
VIB_DEFER_REPAIR = 2800.0
VIB_DEFER_DOWNTIME_HOURS = 10.0

# Speed – compliance / safety coaching (no direct maintenance cost here)
SPEED_EARLY_COACH_COST = 150.0       # half-hour coaching + admin
SPEED_EARLY_DOWNTIME_HOURS = 0.5
SPEED_DEFER_INCIDENT_COST = 1500.0   # incident/citation/insurance hit
SPEED_DEFER_DOWNTIME_HOURS = 4.0

# Pattern-to-risk boost (coolant weighted heavier)
COOLANT_BOOST_LOW = 8.0
COOLANT_BOOST_MED = 18.0
COOLANT_BOOST_HIGH = 32.0

VIB_BOOST_LOW = 5.0
VIB_BOOST_MED = 12.0
VIB_BOOST_HIGH = 20.0

# -------------------------------------------------
# Session state
# -------------------------------------------------

if "scenario_type" not in st.session_state:
    # "coolant_overheat", "vibration_spike", "speed_anomaly", or None
    st.session_state["scenario_type"] = None

if "scenario_started_at" not in st.session_state:
    # ISO string of when this demo scenario began (or None)
    st.session_state["scenario_started_at"] = None


# -------------------------------------------------
# Data access
# -------------------------------------------------


def fetch_telemetry(limit: int = 600) -> pd.DataFrame:
    """
    Pull recent telemetry from the FastAPI backend and normalize timestamps
    to tz-naive for consistent comparisons.
    """
    resp = requests.get(API_URL, params={"limit": limit}, timeout=5)
    resp.raise_for_status()
    data: List[Dict] = resp.json()
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)

    # Parse as UTC then drop tz info so everything is tz-naive
    df["timestamp"] = pd.to_datetime(df["ts"], utc=True).dt.tz_convert(None)
    df = df.sort_values("timestamp")
    return df


def add_validation_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Lightweight validation layer to show that telemetry isn't always perfect."""
    if df.empty:
        df["validation_status"] = []
        df["validation_reason"] = []
        return df

    df = df.copy()
    df["validation_status"] = "Valid"
    df["validation_reason"] = ""

    required = [
        "coolant_temp_f",
        "intake_air_temp_f",
        "engine_rpm",
        "speed_mph",
        "vibration_score",
        "engine_hours",
    ]
    for col in required:
        if col not in df.columns:
            df["validation_status"] = "Rejected"
            df["validation_reason"] = f"Missing required column: {col}"
            return df

    nan_mask = df[required].isna().any(axis=1)
    df.loc[nan_mask, "validation_status"] = "Rejected"
    df.loc[nan_mask, "validation_reason"] = "Missing numeric fields"

    bad_range = (
        (df["coolant_temp_f"] < 150)
        | (df["coolant_temp_f"] > 260)
        | (df["intake_air_temp_f"] < 40)
        | (df["intake_air_temp_f"] > 120)
        | (df["engine_rpm"] < 0)
        | (df["engine_rpm"] > 8000)
        | (df["speed_mph"] < 0)
        | (df["speed_mph"] > 140)
        | (df["vibration_score"] < 0)
        | (df["vibration_score"] > 5)
    )
    df.loc[bad_range & ~nan_mask, "validation_status"] = "Needs review"
    df.loc[bad_range & ~nan_mask, "validation_reason"] = "Out-of-range values"

    return df


def _get_scenario_start_time(df: pd.DataFrame) -> Optional[pd.Timestamp]:
    """
    Convert session_state["scenario_started_at"] into a tz-naive Timestamp
    and clamp it into the range of available telemetry.
    """
    raw = st.session_state.get("scenario_started_at")
    if raw is None or df.empty:
        return None

    # Parse as UTC then drop tz so it matches df["timestamp"]
    try:
        ts = pd.to_datetime(raw, utc=True).tz_convert(None)
    except Exception:
        return None

    min_ts = df["timestamp"].min()
    max_ts = df["timestamp"].max()

    if ts < min_ts:
        ts = min_ts
    if ts > max_ts:
        ts = max_ts
    return ts


def _compute_coolant_pattern_boost(df: pd.DataFrame) -> Dict[str, float]:
    """
    For each vehicle, look at coolant spikes in the demo scenario window.

    - Only consider samples from scenario_start_time up to
      scenario_start_time + COOLANT_PATTERN_WINDOW_SECONDS.
    - High:   frequent spikes, tightly clustered
    - Medium: semi-frequent bursts close together
    - Low:    a few spikes, further apart
    """
    if df.empty:
        return {}

    scenario_start = _get_scenario_start_time(df)
    if scenario_start is None:
        return {}

    window_end = scenario_start + pd.Timedelta(seconds=COOLANT_PATTERN_WINDOW_SECONDS)
    recent = df[(df["timestamp"] >= scenario_start) & (df["timestamp"] <= window_end)]

    if recent.empty:
        return {}

    recent_spikes = recent[recent["coolant_temp_f"] >= COOLANT_SPIKE_THRESHOLD_F]
    if recent_spikes.empty:
        return {}

    boosts: Dict[str, float] = {}

    for vid, grp in recent_spikes.groupby("vehicle_id"):
        grp = grp.sort_values("timestamp")
        n_spikes = len(grp)
        if n_spikes == 0:
            boosts[vid] = 0.0
            continue

        span_sec = (grp["timestamp"].max() - grp["timestamp"].min()).total_seconds()
        if span_sec <= 0:
            span_sec = 1.0

        density = n_spikes / max(span_sec / 30.0, 1.0)

        if n_spikes >= 4 and density >= 2.0:
            boosts[vid] = COOLANT_BOOST_HIGH
        elif n_spikes >= 2 and density >= 1.0:
            boosts[vid] = COOLANT_BOOST_MED
        else:
            boosts[vid] = COOLANT_BOOST_LOW

    return boosts


def _compute_vibration_pattern_boost(df: pd.DataFrame) -> Dict[str, float]:
    """
    For each vehicle, look at vibration spikes in the demo scenario window.

    - Only consider samples from scenario_start_time up to
      scenario_start_time + VIBRATION_PATTERN_WINDOW_SECONDS.
    - High:   many spikes, persistent over time
    - Medium: recurring spikes but less dense
    - Low:    a few notable spikes
    """
    if df.empty:
        return {}

    scenario_start = _get_scenario_start_time(df)
    if scenario_start is None:
        return {}

    window_end = scenario_start + pd.Timedelta(seconds=VIBRATION_PATTERN_WINDOW_SECONDS)
    recent = df[(df["timestamp"] >= scenario_start) & (df["timestamp"] <= window_end)]

    if recent.empty:
        return {}

    recent_spikes = recent[recent["vibration_score"] >= VIBRATION_SPIKE_THRESHOLD]
    if recent_spikes.empty:
        return {}

    boosts: Dict[str, float] = {}

    for vid, grp in recent_spikes.groupby("vehicle_id"):
        grp = grp.sort_values("timestamp")
        n_spikes = len(grp)
        if n_spikes == 0:
            boosts[vid] = 0.0
            continue

        span_sec = (grp["timestamp"].max() - grp["timestamp"].min()).total_seconds()
        if span_sec <= 0:
            span_sec = 1.0

        density = n_spikes / max(span_sec / 60.0, 1.0)

        if n_spikes >= 5 and density >= 2.0:
            boosts[vid] = VIB_BOOST_HIGH
        elif n_spikes >= 3 and density >= 1.0:
            boosts[vid] = VIB_BOOST_MED
        else:
            boosts[vid] = VIB_BOOST_LOW

    return boosts


def add_health_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Derive risk_score [0–100] and risk_band (Low/Medium/High) from
    coolant temp, vibration, engine hours, then adjust based on coolant
    + vibration spike patterns *only within the active scenario window*.
    """
    if df.empty:
        df["risk_score"] = []
        df["risk_band"] = []
        return df

    df = df.copy()

    # Baseline normalization tuned to Corolla-like cruise ranges
    temp_norm = np.clip((df["coolant_temp_f"] - 185) / 25.0, 0, 2)
    vib_norm = np.clip(df["vibration_score"] / 3.0, 0, 2)
    hours_norm = np.clip(df["engine_hours"] / 2000.0, 0, 1)

    df["risk_score"] = (0.5 * temp_norm + 0.3 * vib_norm + 0.2 * hours_norm) * 100.0

    if st.session_state.get("scenario_type") is not None:
        coolant_boosts = _compute_coolant_pattern_boost(df)
        vib_boosts = _compute_vibration_pattern_boost(df)

        df["coolant_pattern_boost"] = df["vehicle_id"].map(coolant_boosts).fillna(0.0)
        df["vibration_pattern_boost"] = df["vehicle_id"].map(vib_boosts).fillna(0.0)

        df["risk_score"] = np.clip(
            df["risk_score"] + df["coolant_pattern_boost"] + df["vibration_pattern_boost"],
            0,
            100,
        )
    else:
        df["coolant_pattern_boost"] = 0.0
        df["vibration_pattern_boost"] = 0.0

    df["risk_band"] = pd.cut(df["risk_score"], bins=RISK_BINS, labels=RISK_LABELS)

    return df


def build_recent_anomaly_view(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build a per-vehicle view of max risk in the last ANOMALY_WINDOW_SECONDS.
    """
    if df.empty:
        return pd.DataFrame(columns=["vehicle_id", "window_risk_score", "window_risk_band"])

    now = df["timestamp"].max()
    window_start = now - pd.Timedelta(seconds=ANOMALY_WINDOW_SECONDS)
    recent = df[df["timestamp"] >= window_start]

    if recent.empty:
        return pd.DataFrame(columns=["vehicle_id", "window_risk_score", "window_risk_band"])

    agg = (
        recent.groupby("vehicle_id")["risk_score"]
        .max()
        .reset_index()
        .rename(columns={"risk_score": "window_risk_score"})
    )
    agg["window_risk_band"] = pd.cut(
        agg["window_risk_score"], bins=RISK_BINS, labels=RISK_LABELS
    )
    return agg


def compute_costs(scenario_type: Optional[str]) -> Tuple[Dict[str, float], Dict[str, float]]:
    """
    Map the current scenario type to early vs deferred costs and downtime.

    Coolant & vibration impact maintenance; speed here is modeled as
    compliance-only (no parts+labor cost).
    """
    early = {"cost": 0.0, "downtime_hours": 0.0}
    deferred = {"cost": 0.0, "downtime_hours": 0.0}

    if scenario_type == "coolant_overheat":
        early_cost = COOLANT_EARLY_REPAIR + COOLANT_EARLY_DOWNTIME_HOURS * (
            LABOR_RATE_PER_HOUR + VEHICLE_REVENUE_PER_HOUR
        )
        defer_cost = COOLANT_DEFER_REPAIR + COOLANT_DEFER_DOWNTIME_HOURS * (
            LABOR_RATE_PER_HOUR + VEHICLE_REVENUE_PER_HOUR
        )

        early = {"cost": early_cost, "downtime_hours": COOLANT_EARLY_DOWNTIME_HOURS}
        deferred = {
            "cost": defer_cost,
            "downtime_hours": COOLANT_DEFER_DOWNTIME_HOURS,
        }

    elif scenario_type == "vibration_spike":
        early_cost = VIB_EARLY_REPAIR + VIB_EARLY_DOWNTIME_HOURS * (
            LABOR_RATE_PER_HOUR + VEHICLE_REVENUE_PER_HOUR
        )
        defer_cost = VIB_DEFER_REPAIR + VIB_DEFER_DOWNTIME_HOURS * (
            LABOR_RATE_PER_HOUR + VEHICLE_REVENUE_PER_HOUR
        )

        early = {"cost": early_cost, "downtime_hours": VIB_EARLY_DOWNTIME_HOURS}
        deferred = {
            "cost": defer_cost,
            "downtime_hours": VIB_DEFER_DOWNTIME_HOURS,
        }

    elif scenario_type == "speed_anomaly":
        # Compliance only in this maintenance-focused model
        early = {"cost": 0.0, "downtime_hours": 0.0}
        deferred = {"cost": 0.0, "downtime_hours": 0.0}

    return early, deferred


# -------------------------------------------------
# UI helpers
# -------------------------------------------------


def render_header(latest_ts: Optional[datetime]) -> None:
    st.set_page_config(page_title=PAGE_TITLE, layout="wide")
    st.title(PAGE_TITLE)
    st.caption(
        "Real-time vehicle telemetry flowing into FastAPI and surfaced as a predictive maintenance dashboard."
    )
    if latest_ts is not None:
        st.caption(f"Last updated: {latest_ts.isoformat(sep=' ', timespec='seconds')}")


def render_data_quality(df: pd.DataFrame) -> None:
    st.markdown("### Data quality overview")
    counts = df["validation_status"].value_counts().to_dict()
    col_v1, col_v2, col_v3 = st.columns(3)
    with col_v1:
        st.metric("Valid", counts.get("Valid", 0))
    with col_v2:
        st.metric("Needs review", counts.get("Needs review", 0))
    with col_v3:
        st.metric("Rejected", counts.get("Rejected", 0))


def scenario_label(scenario_type: Optional[str]) -> str:
    if scenario_type == "coolant_overheat":
        return "Coolant overheat / early water pump failure"
    if scenario_type == "vibration_spike":
        return "Vibration spike / early bearing or suspension issue"
    if scenario_type == "speed_anomaly":
        return "Speed anomaly / driver compliance alert"
    return "No active anomaly scenario"


def render_business_value_panel(
    window_agg: pd.DataFrame, scenario_type: Optional[str]
) -> None:
    total_units = window_agg["vehicle_id"].nunique()
    high_risk = (window_agg["window_risk_band"] == "High").sum()

    early, deferred = compute_costs(scenario_type)

    st.markdown("### Business impact snapshot")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Units in fleet", total_units)
    with c2:
        st.metric("High-risk units (recent)", int(high_risk))
    with c3:
        st.metric("Anomaly window", f"Last {ANOMALY_WINDOW_SECONDS} sec")

    c4, c5 = st.columns(2)
    with c4:
        st.metric("If fixed early (modeled cost)", f"${early['cost']:,.0f}")
        st.metric(
            "Early intervention downtime", f"{early['downtime_hours']:.1f} hrs"
        )
    with c5:
        st.metric(
            "If ignored until failure (modeled cost)", f"${deferred['cost']:,.0f}"
        )
        st.metric(
            "Deferred downtime risk", f"{deferred['downtime_hours']:.1f} hrs"
        )

    st.caption(
        f"Scenario: **{scenario_label(scenario_type)}**. "
        "Costs are modeled per affected vehicle, not per alert. "
        "Coolant patterns are weighted more heavily than vibration, and "
        "both are computed only from telemetry after the current demo "
        "scenario started."
    )


def _trigger_anomaly_backend(anomaly_type: str) -> None:
    """Call the API to inject an anomaly into the telemetry stream."""
    try:
        resp = requests.post(SIM_URL, json={"anomaly_type": anomaly_type}, timeout=3)
        if resp.ok:
            st.success(
                f"Injected {anomaly_type.replace('_', ' ')} anomaly into the stream."
            )
        else:
            st.warning(f"Simulation call returned {resp.status_code}.")
    except Exception as exc:
        st.error(f"Failed to trigger anomaly: {exc}")


def _handle_anomaly_button(anomaly_type: str) -> None:
    """Send anomaly to backend and start a fresh demo scenario."""
    _trigger_anomaly_backend(anomaly_type)
    st.session_state["scenario_type"] = anomaly_type
    st.session_state["scenario_started_at"] = datetime.utcnow().isoformat()
    st.rerun()


def _clear_scenario() -> None:
    st.session_state["scenario_type"] = None
    st.session_state["scenario_started_at"] = None
    st.success("Cleared active anomaly scenario. Risk will return to baseline.")
    st.rerun()


def render_demo_controls() -> None:
    st.markdown("### Demo controls")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("Simulate coolant overheat"):
            _handle_anomaly_button("coolant_overheat")
    with c2:
        if st.button("Simulate vibration spike"):
            _handle_anomaly_button("vibration_spike")
    with c3:
        if st.button("Simulate speed anomaly"):
            _handle_anomaly_button("speed_anomaly")
    with c4:
        if st.button("Reset scenario / costs"):
            _clear_scenario()

    st.caption(
        "Buttons inject anomalies into the stream and start a fresh demo scenario. "
        "Pattern-based risk boosts only use spikes that occur after the scenario "
        "starts. Reset clears the scenario and returns risk to baseline."
    )


def render_anomaly_narrative(scenario_type: Optional[str]) -> None:
    with st.expander("How this anomaly maps to real-world scenarios", expanded=False):
        if scenario_type == "coolant_overheat":
            st.markdown(
                f"""
- **Coolant overheat (pattern-based, scenario-scoped)**  
  Modeled as repeated high-temp events *during this demo scenario* on a delivery vehicle.  
  - Tight, frequent spikes in coolant temperature → **High** pattern intensity.  
  - Bursts of spikes with gaps → **Medium**.  
  - Isolated spikes spread out → **Low**.  
  - If fixed early: ~${COOLANT_EARLY_REPAIR:,.0f} + {COOLANT_EARLY_DOWNTIME_HOURS} hrs of planned downtime.  
  - If ignored: risk of warped head, emulsified oil, severe engine damage, ~${COOLANT_DEFER_REPAIR:,.0f} and {COOLANT_DEFER_DOWNTIME_HOURS} hrs of emergency downtime.
"""
            )
        elif scenario_type == "vibration_spike":
            st.markdown(
                f"""
- **Vibration spike (pattern-based, scenario-scoped)**  
  Modeled as recurring bearing / bushing / suspension / driveline issues in the current scenario window.  
  - Many spikes over a longer window → **High** intensity.  
  - Recurring spikes but less dense → **Medium**.  
  - A few notable spikes → **Low**.  
  - Early: ~${VIB_EARLY_REPAIR:,.0f} + {VIB_EARLY_DOWNTIME_HOURS} hrs scheduled down.  
  - Ignored: major repair, ~${VIB_DEFER_REPAIR:,.0f} and {VIB_DEFER_DOWNTIME_HOURS} hrs down.
"""
            )
        elif scenario_type == "speed_anomaly":
            st.markdown(
                """
- **Speed anomaly (driver behavior / compliance)**  
  Modeled similarly to speeding events in fleet platforms. Speed influences RPM and potential mechanical stress,  
  but here cost modeling stays focused on maintenance. The main value is coaching to prevent tickets and incidents.
"""
            )
        else:
            st.markdown(
                "No active anomaly scenario selected. Use the buttons above to simulate "
                "coolant, vibration, or speed patterns and see how the narrative changes. "
                "Hit reset to return to a clean baseline."
            )


# -------------------------------------------------
# Main layout
# -------------------------------------------------


def main() -> None:
    # Auto-refresh for live background updates
    st_autorefresh(interval=REFRESH_SECONDS * 1000, key="data_refresh")

    try:
        df_raw = fetch_telemetry()
    except Exception as exc:
        st.error(f"Error fetching telemetry from API: {exc}")
        return

    if df_raw.empty:
        render_header(None)
        st.info("Waiting for telemetry from the emulator...")
        st.stop()

    df_valid = add_validation_flags(df_raw)
    df = add_health_signals(df_valid)
    window_agg = build_recent_anomaly_view(df)

    latest_ts = df["timestamp"].max().to_pydatetime()
    render_header(latest_ts)

    scenario_type = st.session_state.get("scenario_type")

    # Top panel: data quality + business impact
    upper_col1, upper_col2 = st.columns([2, 3])
    with upper_col1:
        render_data_quality(df)
    with upper_col2:
        render_business_value_panel(window_agg, scenario_type)

    st.markdown("---")
    render_demo_controls()
    st.markdown("---")

    # Fleet-level overview
    st.markdown("### Fleet risk overview")
    latest_by_unit = (
        df.sort_values("timestamp")
        .groupby("vehicle_id")
        .tail(1)
        .reset_index(drop=True)
    )
    latest_with_window = latest_by_unit.merge(
        window_agg, on="vehicle_id", how="left"
    )

    st.dataframe(
        latest_with_window[
            [
                "vehicle_id",
                "risk_band",
                "risk_score",
                "window_risk_band",
                "window_risk_score",
                "coolant_temp_f",
                "intake_air_temp_f",
                "engine_rpm",
                "speed_mph",
                "vibration_score",
                "engine_hours",
                "validation_status",
            ]
        ].sort_values("window_risk_score", ascending=False),
        hide_index=True,
    )

    # Per-unit detail
    st.markdown("### Per-unit detail")
    unit_ids = sorted(df["vehicle_id"].unique())
    selected_unit = st.selectbox("Select vehicle", unit_ids)
    unit_df = df[df["vehicle_id"] == selected_unit].sort_values("timestamp")

    metric_cols = st.columns(4)
    last_row = unit_df.tail(1).iloc[0]
    with metric_cols[0]:
        st.metric("Risk band (latest)", str(last_row["risk_band"]))
    with metric_cols[1]:
        st.metric("Risk score (latest)", f"{last_row['risk_score']:.1f}")

    unit_window = window_agg[window_agg["vehicle_id"] == selected_unit]
    if not unit_window.empty:
        row_w = unit_window.iloc[0]
        window_band = row_w["window_risk_band"]
        window_score = row_w["window_risk_score"]
    else:
        window_band = "Low"
        window_score = 0.0

    with metric_cols[2]:
        st.metric("Risk band (recent window)", str(window_band))
    with metric_cols[3]:
        st.metric("Risk score (recent window)", f"{window_score:.1f}")

    st.markdown("#### Telemetry trends")
    trend_col1, trend_col2 = st.columns(2)
    with trend_col1:
        st.line_chart(
            unit_df.set_index("timestamp")[["coolant_temp_f", "intake_air_temp_f"]],
            height=260,
        )
    with trend_col2:
        st.line_chart(
            unit_df.set_index("timestamp")[["engine_rpm", "speed_mph"]],
            height=260,
        )

    st.markdown("#### Vibration and raw samples")
    st.line_chart(
        unit_df.set_index("timestamp")[["vibration_score"]],
        height=220,
    )
    st.dataframe(
        unit_df[
            [
                "timestamp",
                "coolant_temp_f",
                "intake_air_temp_f",
                "engine_rpm",
                "speed_mph",
                "vibration_score",
                "engine_hours",
                "risk_band",
                "risk_score",
                "validation_status",
            ]
        ].tail(40),
        hide_index=True,
    )

    render_anomaly_narrative(scenario_type)

    st.caption(
        f"Dashboard refreshes every {REFRESH_SECONDS} seconds; "
        f"risk is based on the last {ANOMALY_WINDOW_SECONDS} seconds of telemetry, "
        "with coolant and vibration patterns computed only from samples after the "
        "current demo scenario started. Reset clears the scenario so bands return "
        "to a clean baseline while preserving historic spikes in the recent window."
    )


if __name__ == "__main__":
    main()
