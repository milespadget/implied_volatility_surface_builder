"""The single entry point: a snapshot in; implied-vol points, surfaces and arbitrage reports out."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ivsurface import arbitrage, black76, chain, svi
from ivsurface.reasons import Reason
from ivsurface.snapshot import to_forward_dollars
from ivsurface.surface import InterpolatedSurface, Surface, SVISurface
from ivsurface.time import year_fraction


@dataclass(frozen=True)
class PipelineResult:
    points: pd.DataFrame
    """One row per input quote: strike, expiry, option_type, k = ln(K/F), T, w = iv^2 T, iv,
    relative_spread = (ask - bid) / mid, mark_iv (carried through from the snapshot), reason.

    Quotes that could not be inverted keep their row, with NaN iv/w and a non-"ok" reason.
    """
    interpolated: InterpolatedSurface | None
    """The baseline surface through the "ok" points, or None if too few quotes survived."""
    interpolated_arbitrage: arbitrage.ArbitrageReport | None
    """Butterfly and calendar violations in ``interpolated`` (None when there is no surface)."""
    svi_params: pd.DataFrame
    """One row per expiry with enough quotes for an SVI fit: T, a, b, rho, m, sigma, min_variance."""
    svi: SVISurface | None
    """The SVI surface built from ``svi_params``, or None if no expiry could be fitted."""
    svi_arbitrage: arbitrage.ArbitrageReport | None
    """Butterfly and calendar violations in ``svi``, over the same quoted k ranges."""


def build(snapshot: pd.DataFrame, config: chain.FilterConfig = chain.FilterConfig()) -> PipelineResult:
    forward = snapshot["underlying_price"].to_numpy(dtype=float)
    strike = snapshot["strike"].to_numpy(dtype=float)
    t = np.array(
        [year_fraction(s, e) for s, e in zip(snapshot["snapshot_time"], snapshot["expiry"], strict=True)]
    )
    bid = snapshot["bid"].to_numpy(dtype=float)
    ask = snapshot["ask"].to_numpy(dtype=float)
    mid = 0.5 * (bid + ask)
    premium = to_forward_dollars(mid, forward)
    option_type = snapshot["option_type"].to_list()
    reasons = chain.screen(snapshot, t, config)
    iv = np.full(len(snapshot), np.nan)
    for i, screen_reason in enumerate(reasons):
        if screen_reason is None:  # passed screening, so invert it
            solved = black76.implied_vol(premium[i], forward[i], strike[i], t[i], option_type[i])
            iv[i], reasons[i] = solved.iv, solved.reason
    points = pd.DataFrame(
        {
            "strike": strike,
            "expiry": snapshot["expiry"].to_numpy(),
            "option_type": option_type,
            "k": np.log(strike / forward),
            "T": t,
            "w": iv**2 * t,
            "iv": iv,
            "relative_spread": chain.relative_spread(bid, ask),
            "mark_iv": snapshot["mark_iv"].to_numpy(dtype=float),
            "reason": [str(r) for r in reasons],
        }
    )
    usable = points.loc[points["reason"] == Reason.OK]

    try:
        interpolated = InterpolatedSurface(usable)
    except ValueError:
        interpolated = None

    svi_slices = _fit_svi_slices(usable)
    svi_surface = SVISurface(svi_slices) if svi_slices else None
    svi_params = pd.DataFrame(
        [{"T": t, **p._asdict(), "min_variance": p.min_variance} for t, p in svi_slices],
        columns=["T", *svi.SVIParams._fields, "min_variance"],
    )

    return PipelineResult(
        points=points,
        interpolated=interpolated,
        interpolated_arbitrage=_check(interpolated, usable),
        svi_params=svi_params,
        svi=svi_surface,
        svi_arbitrage=_check(svi_surface, usable),
    )


def _check(surface: Surface | None, usable: pd.DataFrame) -> arbitrage.ArbitrageReport | None:
    """Arbitrage-check a surface over each of its expiries' quoted k ranges."""
    return None if surface is None else arbitrage.check(surface, _quoted_k_ranges(usable, surface.expiries))


SVI_MIN_QUOTES = 5
"""An SVI slice has five parameters, so an expiry needs at least five usable quotes."""


def _fit_svi_slices(usable: pd.DataFrame) -> list[tuple[float, svi.SVIParams]]:
    """An SVI fit for every expiry with at least SVI_MIN_QUOTES usable quotes."""
    slices = []
    for t in np.unique(usable["T"].to_numpy(dtype=float)):
        slice_points = usable.loc[usable["T"] == t]
        if len(slice_points) >= SVI_MIN_QUOTES:
            slices.append((float(t), svi.fit_slice(slice_points["k"], slice_points["w"], slice_points["relative_spread"])))
    return slices


def _quoted_k_ranges(usable: pd.DataFrame, expiries: np.ndarray) -> list[tuple[float, float]]:
    """For each expiry, the (k_min, k_max) spanned by its usable quotes."""
    ranges = []
    for t in expiries:
        k = usable.loc[usable["T"] == t, "k"].to_numpy(dtype=float)
        ranges.append((float(k.min()), float(k.max())))
    return ranges
