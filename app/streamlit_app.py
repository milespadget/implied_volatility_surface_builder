"""Implied volatility surface explorer. Run with: uv run streamlit run app/streamlit_app.py"""

from datetime import UTC, datetime, timedelta

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from ivsurface.pipeline import build
from ivsurface.synthetic import flat_vol_chain

st.set_page_config(page_title="IV Surface Builder", layout="wide")
st.title("Implied volatility surface builder")
st.caption("Synthetic chain: a single expiry priced at a flat vol, then inverted back with Black-76.")

with st.sidebar:
    forward = st.number_input("Forward F (USD)", value=50_000.0, step=1_000.0, min_value=1.0)
    vol = st.slider("True vol", min_value=0.1, max_value=1.5, value=0.55, step=0.05)
    days = st.slider("Days to expiry", min_value=2, max_value=365, value=30)

snapshot_time = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
# Deribit options expire at 08:00 UTC.
expiry = (snapshot_time + timedelta(days=days)).replace(hour=8)
chain = flat_vol_chain(
    forward=forward,
    vol=vol,
    strikes=list(forward * np.exp(np.linspace(-0.5, 0.5, 21))),
    expiry=expiry,
    snapshot_time=snapshot_time,
)
points = build(chain).points

fig = go.Figure()
for option_type, symbol in (("call", "circle"), ("put", "x")):
    pts = points[points["option_type"] == option_type]
    fig.add_trace(go.Scatter(x=pts["k"], y=pts["iv"], mode="markers", name=option_type, marker_symbol=symbol))
fig.update_layout(xaxis_title="log-moneyness k = ln(K/F)", yaxis_title="implied vol σ", yaxis_tickformat=".0%")
st.plotly_chart(fig, use_container_width=True)
