"""Implied volatility surface explorer. Run with: uv run streamlit run app/streamlit_app.py"""

from datetime import UTC, datetime, timedelta

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from ivsurface.chain import FilterConfig
from ivsurface.pipeline import build
from ivsurface.synthetic import option_chain

EXPIRY_DAYS = [3, 7, 14, 30, 60, 90, 180, 365]

st.set_page_config(page_title="IV Surface Builder", layout="wide")
st.title("Implied volatility surface builder")
st.caption(
    "Synthetic chain from a known vol surface, quoted with a bid/ask spread and noise, screened, "
    "inverted with Black-76 at the mid, then interpolated into a surface."
)

with st.sidebar:
    st.header("True surface")
    forward = st.number_input("Forward F (USD)", value=50_000.0, step=1_000.0, min_value=1.0)
    atm_short = st.slider("ATM vol, shortest expiry", min_value=0.1, max_value=1.5, value=0.7, step=0.05)
    atm_long = st.slider("ATM vol, one year", min_value=0.1, max_value=1.5, value=0.55, step=0.05)
    skew = st.slider("Skew (dσ/dk)", min_value=-0.5, max_value=0.5, value=-0.1, step=0.05)
    curvature = st.slider("Curvature (d²σ/dk²)", min_value=0.0, max_value=2.0, value=0.4, step=0.1)

    st.header("Quotes")
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

t_short, t_long = EXPIRY_DAYS[0] / 365, 1.0


def true_vol(k: float, t: float) -> float:
    """ATM vol moves linearly in sqrt(T) between the two sliders; skew and curvature in k on top."""
    weight = (np.sqrt(t) - np.sqrt(t_short)) / (np.sqrt(t_long) - np.sqrt(t_short))
    atm = atm_short + (atm_long - atm_short) * weight
    return max(atm + skew * k + 0.5 * curvature * k**2, 0.05)


snapshot_time = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
# Deribit options expire at 08:00 UTC.
expiries = [(snapshot_time + timedelta(days=d)).replace(hour=8) for d in EXPIRY_DAYS]
chain = option_chain(
    forward=forward,
    vol=true_vol,
    strikes=list(forward * np.exp(np.linspace(-0.6, 0.6, 25))),
    expiries=expiries,
    snapshot_time=snapshot_time,
    relative_spread=spread,
    noise=noise,
    seed=42,
)
result = build(chain, config)
points = result.points
used = points.query("reason == 'ok'")
surface = result.interpolated

smiles_tab, surface_tab, term_tab = st.tabs(["Smiles by expiry", "3D surface", "ATM term structure"])

with smiles_tab:
    fig = go.Figure()
    for days, (t, slice_points) in zip(EXPIRY_DAYS, points.groupby("T", sort=True), strict=True):
        ok = slice_points.query("reason == 'ok'")
        name = f"{days}d"
        fig.add_trace(go.Scatter(x=ok["k"], y=ok["iv"], mode="markers", name=name, legendgroup=name))
        if surface is not None and len(ok) >= 2:
            k = np.linspace(ok["k"].min(), ok["k"].max(), 200)
            fig.add_trace(
                go.Scatter(
                    x=k, y=surface.iv(k, np.full_like(k, t)), mode="lines", name=f"{name} interpolated",
                    legendgroup=name, showlegend=False, line={"width": 1},
                )
            )
    fig.update_layout(xaxis_title="log-moneyness k = ln(K/F)", yaxis_title="implied vol σ", yaxis_tickformat=".0%")
    st.plotly_chart(fig, use_container_width=True)

if surface is None:
    st.warning("Too few quotes survived the filters to build a surface.")
else:
    k_grid = np.linspace(-0.6, 0.6, 61)
    t_grid = np.linspace(surface.expiries[0], surface.expiries[-1], 60)
    kk, tt = np.meshgrid(k_grid, t_grid)

    with surface_tab:
        fig = go.Figure(go.Surface(x=kk, y=tt * 365, z=surface.iv(kk, tt), colorscale="Viridis", colorbar={"title": "σ"}))
        fig.add_trace(
            go.Scatter3d(x=used["k"], y=used["T"] * 365, z=used["iv"], mode="markers", marker={"size": 2, "color": "black"}, name="quotes")
        )
        fig.update_layout(
            scene={"xaxis_title": "k = ln(K/F)", "yaxis_title": "days to expiry", "zaxis_title": "σ", "zaxis_tickformat": ".0%"},
            height=650,
        )
        st.plotly_chart(fig, use_container_width=True)

    with term_tab:
        fig = go.Figure(go.Scatter(x=t_grid * 365, y=surface.iv(np.zeros_like(t_grid), t_grid), mode="lines", name="interpolated"))
        fig.add_trace(
            go.Scatter(x=t_grid * 365, y=[true_vol(0.0, t) for t in t_grid], mode="lines", line={"dash": "dot"}, name="true")
        )
        fig.update_layout(xaxis_title="days to expiry", yaxis_title="ATM implied vol σ(k=0)", yaxis_tickformat=".0%")
        st.plotly_chart(fig, use_container_width=True)

st.subheader("Quotes")
st.write(f"{len(used)} of {len(points)} quotes inverted. The rest were rejected:")
rejected = points.query("reason != 'ok'")["reason"].value_counts().rename_axis("reason").reset_index(name="quotes")
st.dataframe(rejected, hide_index=True)
