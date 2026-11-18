"""The single entry point: a snapshot in, implied-vol points (and later, surfaces) out."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ivsurface import black76, chain
from ivsurface.snapshot import to_forward_dollars
from ivsurface.surface import InterpolatedSurface
from ivsurface.time import year_fraction


@dataclass(frozen=True)
class PipelineResult:
    points: pd.DataFrame
    """One row per input quote: strike, expiry, option_type, k = ln(K/F), T, w = iv^2 T, iv,
    relative_spread = (ask - bid) / mid, reason.

    Quotes that could not be inverted keep their row, with NaN iv/w and a non-"ok" reason.
    """
    interpolated: InterpolatedSurface | None
    """The baseline surface through the "ok" points, or None if too few quotes survived."""


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
    reason = chain.screen(snapshot, t, config)
    iv = np.full(len(snapshot), np.nan)
    for i, rejected in enumerate(reason):
        if rejected is None:
            solved = black76.implied_vol(premium[i], forward[i], strike[i], t[i], option_type[i])
            iv[i], reason[i] = solved.iv, str(solved.reason)
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
            "reason": reason,
        }
    )
    usable = points.query("reason == 'ok'")
    try:
        interpolated = InterpolatedSurface(usable)
    except ValueError:
        interpolated = None
    return PipelineResult(points=points, interpolated=interpolated)
