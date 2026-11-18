"""The single entry point: a snapshot in; implied-vol points, surfaces and arbitrage reports out."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ivsurface import arbitrage, black76, chain
from ivsurface.reasons import Reason
from ivsurface.snapshot import to_forward_dollars
from ivsurface.surface import InterpolatedSurface
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
        return PipelineResult(points=points, interpolated=None, interpolated_arbitrage=None)
    return PipelineResult(
        points=points,
        interpolated=interpolated,
        interpolated_arbitrage=arbitrage.check(interpolated, _quoted_k_ranges(usable, interpolated.expiries)),
    )


def _quoted_k_ranges(usable: pd.DataFrame, expiries: np.ndarray) -> list[tuple[float, float]]:
    """For each expiry, the (k_min, k_max) spanned by its usable quotes."""
    ranges = []
    for t in expiries:
        k = usable.loc[usable["T"] == t, "k"].to_numpy(dtype=float)
        ranges.append((float(k.min()), float(k.max())))
    return ranges
