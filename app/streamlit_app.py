"""Implied volatility surface explorer. Run with: uv run streamlit run app/streamlit_app.py"""

from datetime import UTC, datetime, timedelta

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from ivsurface.chain import FilterConfig
from ivsurface.pipeline import build
from ivsurface.synthetic import flat_vol_chain

st.set_page_config(page_title="IV Surface Builder", layout="wide")
st.title("Implied volatility surface builder")
st.caption(
    "Synthetic chain: a single expiry priced at a flat vol, quoted with a bid/ask spread and noise, "
    "screened, then inverted back with Black-76 at the mid."
)

with st.sidebar:
    st.header("Synthetic chain")
    forward = st.number_input("Forward F (USD)", value=50_000.0, step=1_000.0, min_value=1.0)
    vol = st.slider("True vol", min_value=0.1, max_value=1.5, value=0.55, step=0.05)
    days = st.slider("Days to expiry", min_value=1, max_value=365, value=30)
    spread = st.slider("Bid/ask spread (relative)", min_value=0.0, max_value=1.0, value=0.1, step=0.01)
    noise = st.slider("Mid-price noise (relative)", min_value=0.0, max_value=0.1, value=0.01, step=0.005)

    st.header("Filters")
    defaults = FilterConfig()
    config = FilterConfig(
        min_bid=st.number_input("Minimum bid (BTC)", value=defaults.min_bid, min_value=0.0, step=0.0001, format="%.4f"),
        max_relative_spread=st.slider(
            "Max relative spread", min_value=0.0, max_value=2.0, value=defaults.max_relative_spread, step=0.05
        ),
        min_days_to_expiry=st.slider(
            "Min days to expiry", min_value=0.0, max_value=14.0, value=defaults.min_days_to_expiry, step=0.5
        ),
    )

snapshot_time = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
# Deribit options expire at 08:00 UTC.
expiry = (snapshot_time + timedelta(days=days)).replace(hour=8)
chain = flat_vol_chain(
    forward=forward,
    vol=vol,
    strikes=list(forward * np.exp(np.linspace(-0.5, 0.5, 21))),
    expiry=expiry,
    snapshot_time=snapshot_time,
    relative_spread=spread,
    noise=noise,
    seed=42,
)
points = build(chain, config).points
used = points.query("reason == 'ok'")

fig = go.Figure()
for option_type, symbol in (("call", "circle"), ("put", "x")):
    pts = used.query("option_type == @option_type")
    fig.add_trace(go.Scatter(x=pts["k"], y=pts["iv"], mode="markers", name=f"OTM {option_type}s", marker_symbol=symbol))
fig.add_hline(y=vol, line_dash="dot", annotation_text="true vol")
fig.update_layout(xaxis_title="log-moneyness k = ln(K/F)", yaxis_title="implied vol σ", yaxis_tickformat=".0%")
st.plotly_chart(fig, use_container_width=True)

st.subheader("Quotes")
st.write(f"{len(used)} of {len(points)} quotes inverted. The rest were rejected:")
rejected = points.query("reason != 'ok'")["reason"].value_counts().rename_axis("reason").reset_index(name="quotes")
st.dataframe(rejected, hide_index=True)
