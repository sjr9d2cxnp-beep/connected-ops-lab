# dashboard.py
import streamlit as st
import pandas as pd
import requests
import plotly.express as px

API_URL = "http://127.0.0.1:8000/telemetry"

st.title("Corolla Telemetry MVP")

data = requests.get(API_URL).json()
df = pd.DataFrame(data)

if df.empty:
    st.write("No data yet.")
else:
    df["ts"] = pd.to_datetime(df["ts"])

    st.subheader("Latest Values")
    st.write(df.tail(1))

    st.subheader("RPM Over Time")
    fig = px.line(df, x="ts", y="rpm")
    st.plotly_chart(fig)

    st.subheader("Coolant Temp Over Time")
    fig2 = px.line(df, x="ts", y="coolant_temp_c")
    st.plotly_chart(fig2)

    st.subheader("Speed Over Time")
    fig3 = px.line(df, x="ts", y="speed_mph")
    st.plotly_chart(fig3)
