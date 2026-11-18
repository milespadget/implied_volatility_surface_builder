"""Implied volatility surface explorer. Run with: uv run streamlit run app/streamlit_app.py

Saved Deribit snapshots are read from (and fetched into) data/snapshots, or the directory named
by the IVSURFACE_SNAPSHOT_DIR environment variable.
"""

import os
import urllib.error
from datetime import UTC, datetime, timedelta
from pathlib import Path
from collections.abc import Mapping
from typing import NamedTuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ivsurface.arbitrage import ArbitrageReport, ViolationKind
from ivsurface.chain import FilterConfig
from ivsurface.data import fetch_snapshot, list_snapshots, load_snapshot, save_snapshot
from ivsurface.pipeline import PipelineResult, build
from ivsurface.surface import Surface
from ivsurface.synthetic import VolFunction, option_chain

SYNTHETIC = "Synthetic surface"
SYNTHETIC_EXPIRY_DAYS = [3, 7, 14, 30, 60, 90, 180, 365]
SNAPSHOT_DIR = Path(os.environ.get("IVSURFACE_SNAPSHOT_DIR", "data/snapshots"))

st.set_page_config(page_title="IV Surface Builder", layout="wide")
st.title("Implied volatility surface builder")


def synthetic_snapshot() -> tuple[pd.DataFrame, VolFunction]:
    """Sidebar controls for a known true surface, and the chain quoted from it."""
    st.header("True surface")
    forward = st.number_input("Forward F (USD)", value=50_000.0, step=1_000.0, min_value=1.0)
    atm_short = st.slider("ATM vol, shortest expiry", min_value=0.1, max_value=1.5, value=0.7, step=0.05)
    atm_long = st.slider("ATM vol, one year", min_value=0.1, max_value=1.5, value=0.55, step=0.05)
    skew = st.slider("Skew (dσ/dk)", min_value=-0.5, max_value=0.5, value=-0.1, step=0.05)
    curvature = st.slider("Curvature (d²σ/dk²)", min_value=0.0, max_value=2.0, value=0.4, step=0.1)

    st.header("Quotes")
    spread = st.slider("Bid/ask spread (relative)", min_value=0.0, max_value=1.0, value=0.1, step=0.01)
    noise = st.slider("Mid-price noise (relative)", min_value=0.0, max_value=0.1, value=0.01, step=0.005)

    t_short, t_long = SYNTHETIC_EXPIRY_DAYS[0] / 365, 1.0

    def true_vol(k: float, t: float) -> float:
        """ATM vol moves linearly in sqrt(T) between the two sliders; skew and curvature in k on top."""
        weight = (np.sqrt(t) - np.sqrt(t_short)) / (np.sqrt(t_long) - np.sqrt(t_short))
        atm = atm_short + (atm_long - atm_short) * weight
        return max(atm + skew * k + 0.5 * curvature * k**2, 0.05)

    snapshot_time = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    expiries = [(snapshot_time + timedelta(days=d)).replace(hour=8) for d in SYNTHETIC_EXPIRY_DAYS]
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
    return chain, true_vol


with st.sidebar:
    st.header("Data")
    underlying = st.selectbox("Underlying to fetch", ["BTC", "ETH"])
    if st.button(f"Fetch {underlying} chain from Deribit"):
        try:
            saved = save_snapshot(fetch_snapshot(underlying), SNAPSHOT_DIR)
            st.session_state["source"] = saved.name
        except (urllib.error.URLError, TimeoutError) as error:
            st.error(f"Could not reach Deribit: {error}")
    saved_snapshots = {p.name: p for p in reversed(list_snapshots(SNAPSHOT_DIR))}  # newest first
    source = st.selectbox("Data source", [SYNTHETIC, *saved_snapshots], key="source")

    true_vol: VolFunction | None = None
    if source == SYNTHETIC:
        snapshot, true_vol = synthetic_snapshot()
    else:
        snapshot = load_snapshot(saved_snapshots[source])

    st.header("Filters")
    defaults = FilterConfig()
    config = FilterConfig(
        min_bid=st.number_input(
            "Minimum bid (units of the underlying)", value=defaults.min_bid, min_value=0.0, step=0.0001, format="%.4f"
        ),
        max_relative_spread=st.slider(
            "Max relative spread", min_value=0.0, max_value=2.0, value=defaults.max_relative_spread, step=0.05
        ),
        min_days_to_expiry=st.slider(
            "Min days to expiry", min_value=0.0, max_value=14.0, value=defaults.min_days_to_expiry, step=0.5
        ),
    )

if source == SYNTHETIC:
    st.caption(
        "Synthetic chain from a known vol surface, quoted with a bid/ask spread and noise, screened, "
        "inverted with Black-76 at the mid, then interpolated into a surface."
    )
else:
    taken = snapshot["snapshot_time"].iat[0]
    st.caption(
        f"Deribit {snapshot['underlying'].iat[0]} options at {taken:%Y-%m-%d %H:%M} UTC, screened, inverted with "
        "Black-76 at the mid, then interpolated into a surface. Our IVs come from mid prices; Deribit's mark IV "
        "comes from its own mark price, so expect small gaps between the two, mostly where spreads are wide."
    )

@st.cache_resource(max_entries=16, show_spinner="Inverting quotes and fitting SVI slices…")
def build_cached(snapshot: pd.DataFrame, config: FilterConfig) -> PipelineResult:
    """The pipeline is deterministic, so a slider change only refits when its inputs change."""
    return build(snapshot, config)


class SurfaceView(NamedTuple):
    """One surface the pipeline built, with how the app draws it."""

    label: str
    surface: Surface
    report: ArbitrageReport
    line: Mapping[str, object]


result = build_cached(snapshot, config)
points = result.points
used = points.query("reason == 'ok'")
views = [
    SurfaceView(label, surface, report, line)
    for label, surface, report, line in (
        ("SVI", result.svi, result.svi_arbitrage, {"width": 2, "dash": "dash"}),
        ("Interpolated", result.interpolated, result.interpolated_arbitrage, {"width": 1}),
    )
    if surface is not None and report is not None
]

smiles_tab, surface_tab, term_tab, arbitrage_tab = st.tabs(
    ["Smiles by expiry", "3D surface", "ATM term structure", "Arbitrage"]
)

with smiles_tab:
    fig = go.Figure()
    for t in np.unique(used["T"].to_numpy(dtype=float)):
        ok = used.loc[used["T"] == t]
        name = f"{t * 365:.1f}d"
        fig.add_trace(go.Scatter(x=ok["k"], y=ok["iv"], mode="markers", name=name, legendgroup=name))
        fig.add_trace(
            go.Scatter(
                x=ok["k"], y=ok["mark_iv"], mode="markers", name=f"{name} Deribit mark IV", legendgroup=name,
                showlegend=False, marker={"symbol": "circle-open", "color": "grey"},
            )
        )
        k = np.linspace(ok["k"].min(), ok["k"].max(), 200)
        for view in views:
            if t in view.surface.expiries:
                fig.add_trace(
                    go.Scatter(
                        x=k, y=view.surface.iv(k, np.full_like(k, t)), mode="lines", name=f"{name} {view.label}",
                        legendgroup=name, showlegend=False, line=view.line,
                    )
                )
    fig.update_layout(xaxis_title="log-moneyness k = ln(K/F)", yaxis_title="implied vol σ", yaxis_tickformat=".0%")
    st.plotly_chart(fig, width="stretch")
    st.caption(
        "Filled markers: our IV at the mid. Open grey markers: Deribit's mark IV. "
        "Dashed lines: the SVI fit. Thin lines: the interpolated surface."
    )

if not views:
    st.warning("Too few quotes survived the filters to build a surface.")
else:
    main = views[0]  # SVI when it could be fitted, otherwise the interpolated surface
    k_lo, k_hi = np.quantile(used["k"], [0.02, 0.98])
    k_grid = np.linspace(k_lo, k_hi, 61)
    all_expiries = np.concatenate([v.surface.expiries for v in views])
    t_grid = np.linspace(all_expiries.min(), all_expiries.max(), 60)
    kk, tt = np.meshgrid(k_grid, t_grid)

    with surface_tab:
        fig = go.Figure(go.Surface(x=kk, y=tt * 365, z=main.surface.iv(kk, tt), colorscale="Viridis", colorbar={"title": "σ"}))
        fig.add_trace(
            go.Scatter3d(x=used["k"], y=used["T"] * 365, z=used["iv"], mode="markers", marker={"size": 2, "color": "black"}, name="quotes")
        )
        fig.update_layout(
            scene={"xaxis_title": "k = ln(K/F)", "yaxis_title": "days to expiry", "zaxis_title": "σ", "zaxis_tickformat": ".0%"},
            height=650,
        )
        st.plotly_chart(fig, width="stretch")
        st.caption(f"The {main.label} surface, with the quotes it was built from.")

    with term_tab:
        fig = go.Figure()
        for view in views:
            fig.add_trace(
                go.Scatter(x=t_grid * 365, y=view.surface.iv(np.zeros_like(t_grid), t_grid), mode="lines", name=view.label, line=view.line)
            )
        if true_vol is not None:
            fig.add_trace(
                go.Scatter(x=t_grid * 365, y=[true_vol(0.0, t) for t in t_grid], mode="lines", line={"dash": "dot"}, name="true")
            )
        fig.update_layout(xaxis_title="days to expiry", yaxis_title="ATM implied vol σ(k=0)", yaxis_tickformat=".0%")
        st.plotly_chart(fig, width="stretch")

    with arbitrage_tab:
        columns = iter(st.columns(2 * len(views)))
        for view in sorted(views, key=lambda v: v.label):  # Interpolated first: the baseline, then SVI
            for kind in (ViolationKind.BUTTERFLY, ViolationKind.CALENDAR):
                next(columns).metric(
                    f"{view.label}: {kind}", view.report.count(kind),
                    f"{view.report.share(kind):.0%} of points checked", delta_color="off",
                )
        st.caption(
            "Butterfly: Durrleman's g(k) < 0 on a slice means the smile implies a negative density. "
            "Calendar: total variance w = σ²T falling as expiry lengthens at fixed k. "
            "Counts are grid points in violation over each expiry's quoted k range. SVI needs at least "
            "five quotes per expiry, so it may cover fewer expiries than the interpolated surface."
        )

        by_label = {v.label: v for v in views}
        inspect = st.radio("Inspect", list(by_label), horizontal=True, key="inspect")
        report = by_label[inspect].report
        fig = go.Figure()
        for curve in report.butterfly_curves:
            fig.add_trace(go.Scatter(x=curve.k, y=curve.g, mode="lines", name=f"{curve.t * 365:.1f}d"))
        fig.add_hline(y=0, line_color="red", annotation_text="g = 0")
        fig.update_layout(xaxis_title="log-moneyness k = ln(K/F)", yaxis_title=f"Durrleman g(k), {inspect}")
        st.plotly_chart(fig, width="stretch")

        worst = report.violations.sort_values("magnitude", ascending=False).head(20).assign(days=lambda v: v["T"] * 365)
        st.dataframe(worst[["kind", "k", "days", "magnitude"]], hide_index=True)

    st.subheader("SVI slices")
    st.dataframe(result.svi_params.assign(days=lambda p: p["T"] * 365).drop(columns="T"), hide_index=True)

st.subheader("Quotes")
st.write(f"{len(used)} of {len(points)} quotes inverted. The rest were rejected:")
rejected = points.query("reason != 'ok'")["reason"].value_counts().rename_axis("reason").reset_index(name="quotes")
st.dataframe(rejected, hide_index=True)
