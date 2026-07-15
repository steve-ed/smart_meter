import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from anomaly_detector import detect_anomalies

st.set_page_config(page_title="Energy Anomaly Monitor", layout="wide")


@st.cache_data
def load_data() -> pd.DataFrame:
    df = pd.read_csv("data/consumption_clean.csv")
    df["timestamp"] = pd.to_datetime(df["timestamp"], format="%Y-%m-%d %H:%M")
    return df


@st.cache_data
def get_anomalies(_df: pd.DataFrame) -> pd.DataFrame:
    # Underscore prefix tells Streamlit not to hash this arg.
    # Result is computed once at startup and cached for the session.
    return detect_anomalies(_df)


df = load_data()
anomalies = get_anomalies(df)

# Sidebar
st.sidebar.title("Filters")

mpxn = st.sidebar.selectbox("MPxN", sorted(df["mpxn"].unique()))

available_utilities = sorted(df[df["mpxn"] == mpxn]["utility"].unique().tolist())
utility_opts = ["both"] + available_utilities
utility = st.sidebar.selectbox("Utility", utility_opts)

anomaly_type = st.sidebar.selectbox(
    "Anomaly type", ["all", "spike", "prolonged", "flat_line"]
)

# Filter anomalies
filtered = anomalies[anomalies["mpxn"] == mpxn].copy()
if utility != "both":
    filtered = filtered[filtered["utility"] == utility]
if anomaly_type != "all":
    filtered = filtered[filtered["anomaly_type"] == anomaly_type]

# Summary cards
st.title(f"Energy Anomaly Monitor — {mpxn}")

col1, col2, col3 = st.columns(3)
col1.metric("Spikes",     int((filtered["anomaly_type"] == "spike").sum()))
col2.metric("Prolonged",  int((filtered["anomaly_type"] == "prolonged").sum()))
col3.metric("Flat-lines", int((filtered["anomaly_type"] == "flat_line").sum()))

# Timeline chart
st.subheader("Consumption timeline")

consumption = df[df["mpxn"] == mpxn].copy()
if utility != "both":
    consumption = consumption[consumption["utility"] == utility]

daily = (
    consumption
    .assign(date=consumption["timestamp"].dt.date)
    .groupby(["date", "utility"])["value"]
    .sum()
    .reset_index()
)

UTILITY_COLOURS = {"electricity": "#209dd7", "gas": "#753991"}
MARKER_COLOURS  = {"spike": "red", "prolonged": "orange", "flat_line": "gray"}
MARKER_LABELS   = {"spike": "Spike", "prolonged": "Prolonged", "flat_line": "Flat-line"}

fig = go.Figure()

for u, u_daily in daily.groupby("utility"):
    fig.add_trace(go.Scatter(
        x=u_daily["date"],
        y=u_daily["value"],
        name=u.capitalize(),
        line=dict(color=UTILITY_COLOURS.get(u, "#888888")),
    ))

y_max = daily["value"].max() if not daily.empty else 1.0
for atype, agroup in filtered.groupby("anomaly_type"):
    fig.add_trace(go.Scatter(
        x=agroup["timestamp"].dt.date,
        y=[y_max * 0.95] * len(agroup),
        mode="markers",
        name=MARKER_LABELS.get(atype, atype),
        marker=dict(
            color=MARKER_COLOURS.get(atype, "black"),
            size=10,
            symbol="triangle-down",
        ),
    ))

fig.update_layout(
    xaxis_title="Date",
    yaxis_title="Consumption",
    height=420,
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
)
st.plotly_chart(fig, use_container_width=True)

# Events table
st.subheader("Anomaly events")

if filtered.empty:
    st.info("No anomalies detected for the current selection.")
else:
    display = filtered.copy().sort_values("timestamp", ascending=False)
    display["ratio"] = display["ratio"].apply(
        lambda x: f"{x:.1f}x" if pd.notna(x) else "-"
    )
    display["baseline"] = display["baseline"].apply(
        lambda x: f"{x:.3f}" if pd.notna(x) else "-"
    )
    display["timestamp"] = display["timestamp"].dt.strftime("%Y-%m-%d %H:%M")
    st.dataframe(
        display[["timestamp", "utility", "anomaly_type", "value", "baseline", "ratio"]],
        use_container_width=True,
        hide_index=True,
    )
