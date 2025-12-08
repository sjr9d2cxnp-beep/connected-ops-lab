import os
from datetime import datetime

import numpy as np
import pandas as pd
import requests
import streamlit as st

# =====================================================
# Config
# =====================================================

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000/telemetry")
PAGE_TITLE = "Connected Ops Lab"
REFRESH_SECONDS = 15


# =====================================================
# Data layer
# =====================================================

def fetch_telemetry(api_url: str = API_URL) -> pd.DataFrame:
    """
    Pull raw telemetry from the FastAPI service.

    Expected JSON shape: list[dict] with fields like:
      - ts (ISO timestamp) or timestamp
      - coolant_temp_f
      - intake_air_temp_f
      - engine_rpm
      - speed_mph
      - vibration_score
      - engine_hours
      - vehicle_id (optional; defaulted if missing)

    If the API returns nothing or errors, we bubble that up instead
    of silently faking data.
    """
    try:
        resp = requests.get(api_url, timeout=3)
        resp.raise_for_status()
    except Exception as exc:
        raise RuntimeError(f"Error calling telemetry API: {exc}") from exc

    data = resp.json()
    if not data:
        raise RuntimeError("Telemetry API returned an empty payload.")

    df = pd.DataFrame(data)

    # Normalize timestamp
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    elif "ts" in df.columns:
        df["timestamp"] = pd.to_datetime(df["ts"])
        df = df.drop(columns=["ts"])
    else:
        raise RuntimeError("Telemetry payload is missing 'timestamp' or 'ts' field.")

    # Ensure vehicle_id exists (single-vehicle emulator defaults to Corolla-2019)
    if "vehicle_id" not in df.columns:
        df["vehicle_id"] = "Corolla-2019"

    # Sort for later rolling windows & UI
    df = df.sort_values(["vehicle_id", "timestamp"]).reset_index(drop=True)
    return df


def add_health_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add rule-based anomaly flags and a simple risk score.

    Rules are tuned to feel like a 2019 Corolla cruising at highway speeds.
    """
    df = df.copy()

    # Hard per-sample limits
    df["coolant_high"] = df["coolant_temp_f"] > 220.0          # clearly too hot
    df["intake_high"] = df["intake_air_temp_f"] > 120.0        # intake way above ambient
    df["vibration_high"] = df["vibration_score"] > 1.0         # noticeable roughness

    # Rolling trends (~10 minutes at ~1 Hz)
    df["coolant_rolling"] = (
        df.groupby("vehicle_id")["coolant_temp_f"]
        .rolling(window=600, min_periods=60)
        .mean()
        .reset_index(level=0, drop=True)
    )
    df["intake_rolling"] = (
        df.groupby("vehicle_id")["intake_air_temp_f"]
        .rolling(window=600, min_periods=60)
        .mean()
        .reset_index(level=0, drop=True)
    )

    df["coolant_trend_high"] = df["coolant_rolling"] > 210.0
    df["intake_trend_high"] = df["intake_rolling"] > 90.0

    # Risk score: simple weighted sum of flags
    df["risk_score"] = (
        df["coolant_high"].astype(int) * 3
        + df["coolant_trend_high"].astype(int) * 2
        + df["intake_high"].astype(int) * 2
        + df["intake_trend_high"].astype(int) * 1
        + df["vibration_high"].astype(int) * 3
    )

    def classify(score: int) -> str:
        if score >= 6:
            return "High"
        if score >= 3:
            return "Medium"
        return "Low"

    df["risk_band"] = df["risk_score"].apply(classify)
    return df


def load_lab_data() -> pd.DataFrame:
    """
    End-to-end data loader for the lab.

    - Pulls live telemetry from the FastAPI emulator
    - Adds health signals & risk bands
    - Never falls back to fake / simulated data
    """
    df_raw = fetch_telemetry()
    df = add_health_signals(df_raw)
    return df


# =====================================================
# UI helpers
# =====================================================

def render_header(latest_ts: datetime) -> None:
    st.title(PAGE_TITLE)
    st.caption(
        "Live OBD-II telemetry from a 2019 Corolla → rule-based health signals → "
        "maintenance priorities. Built as a Connected Ops demo for SE conversations."
    )
    st.info(f"Data source: **live FastAPI emulator** • Last sample: `{latest_ts}`")


def render_sidebar(df: pd.DataFrame) -> tuple[str, list[str]]:
    st.sidebar.header("Filters")

    vehicle_ids = sorted(df["vehicle_id"].unique())
    selected_vehicle = st.sidebar.selectbox("Select unit", vehicle_ids)

    risk_filter = st.sidebar.multiselect(
        "Filter fleet by risk band",
        options=["High", "Medium", "Low"],
        default=["High", "Medium", "Low"],
    )
    return selected_vehicle, risk_filter


def render_fleet_snapshot(df: pd.DataFrame, risk_filter: list[str]) -> None:
    st.subheader("Fleet health snapshot")

    # Latest row per vehicle
    latest = (
        df.sort_values("timestamp")
        .groupby("vehicle_id")
        .tail(1)
        .reset_index(drop=True)
    )

    if risk_filter:
        latest = latest[latest["risk_band"].isin(risk_filter)]

    vehicle_ids = df["vehicle_id"].unique()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Units monitored", value=len(vehicle_ids))
    with col2:
        st.metric("High-risk units", int((latest["risk_band"] == "High").sum()))
    with col3:
        st.metric("Medium-risk units", int((latest["risk_band"] == "Medium").sum()))

    st.markdown("### Maintenance priority list")

    priority_cols = [
        "vehicle_id",
        "risk_band",
        "risk_score",
        "coolant_temp_f",
        "intake_air_temp_f",
        "vibration_score",
        "timestamp",
    ]

    latest_sorted = latest.sort_values(
        ["risk_score", "coolant_temp_f", "intake_air_temp_f", "vehicle_id"],
        ascending=[False, False, False, True],
    )

    st.dataframe(
        latest_sorted[priority_cols].reset_index(drop=True),
        use_container_width=True,
    )


def render_unit_detail(df: pd.DataFrame, vehicle_id: str) -> None:
    unit_df = df[df["vehicle_id"] == vehicle_id].sort_values("timestamp")
    if unit_df.empty:
        st.warning(f"No data available for `{vehicle_id}`.")
        return

    st.markdown(f"### Unit detail: `{vehicle_id}`")

    latest = unit_df.iloc[-1]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Risk band", latest["risk_band"])
    with c2:
        st.metric("Coolant temp (°F)", f"{latest['coolant_temp_f']:.1f}")
    with c3:
        st.metric("Intake air (°F)", f"{latest['intake_air_temp_f']:.1f}")
    with c4:
        st.metric("Vibration score", f"{latest['vibration_score']:.2f}")

    c5, c6 = st.columns(2)
    with c5:
        st.metric("Engine RPM", int(latest["engine_rpm"]))
    with c6:
        st.metric("Engine hours", f"{latest['engine_hours']:.2f}")

    st.markdown("#### Trend lines")

    plot_df = unit_df.set_index("timestamp").copy()
    plot_df["coolant_temp_smooth"] = (
        plot_df["coolant_temp_f"].rolling(window=20, min_periods=1).mean()
    )
    plot_df["intake_air_smooth"] = (
        plot_df["intake_air_temp_f"].rolling(window=20, min_periods=1).mean()
    )
    plot_df["vibration_smooth"] = (
        plot_df["vibration_score"].rolling(window=20, min_periods=1).mean()
    )

    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.line_chart(
            plot_df[["coolant_temp_smooth", "intake_air_smooth"]],
            height=260,
        )
    with chart_col2:
        st.line_chart(
            plot_df[["vibration_smooth"]],
            height=260,
        )

    st.markdown("#### Recent raw telemetry")
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
                "risk_score",
                "risk_band",
            ]
        ].tail(100),
        use_container_width=True,
    )


# =====================================================
# Main
# =====================================================

def main() -> None:
    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon="🛠️",
        layout="wide",
    )

    # simple auto-refresh so the lab feels live
    st.markdown(
        f"""
        <meta http-equiv="refresh" content="{REFRESH_SECONDS}">
        """,
        unsafe_allow_html=True,
    )

    try:
        df = load_lab_data()
    except RuntimeError as err:
        st.title(PAGE_TITLE)
        st.error(
            f"Unable to load live telemetry.\n\n"
            f"{err}\n\n"
            "Make sure Docker is running and the FastAPI emulator container is healthy."
        )
        return

    if df.empty:
        st.title(PAGE_TITLE)
        st.error("Telemetry dataframe is empty after processing.")
        return

    latest_ts = df["timestamp"].max()
    render_header(latest_ts)

    selected_vehicle, risk_filter = render_sidebar(df)
    render_fleet_snapshot(df, risk_filter)
    render_unit_detail(df, selected_vehicle)


if __name__ == "__main__":
    main()
