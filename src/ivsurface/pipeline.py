"""The single entry point: a snapshot in, implied-vol points (and later, surfaces) out."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ivsurface import black76
from ivsurface.snapshot import to_forward_dollars
from ivsurface.time import year_fraction


@dataclass(frozen=True)
class PipelineResult:
    points: pd.DataFrame
    """One row per input quote: strike, expiry, option_type, k = ln(K/F), T, w = iv^2 T, iv."""


def build(snapshot: pd.DataFrame) -> PipelineResult:
    forward = snapshot["underlying_price"].to_numpy(dtype=float)
    strike = snapshot["strike"].to_numpy(dtype=float)
    t = np.array(
        [year_fraction(s, e) for s, e in zip(snapshot["snapshot_time"], snapshot["expiry"], strict=True)]
    )
    mid = 0.5 * (snapshot["bid"].to_numpy(dtype=float) + snapshot["ask"].to_numpy(dtype=float))
    premium = to_forward_dollars(mid, forward)
    iv = np.array(
        [
            black76.implied_vol(prem, fwd, strk, years, option_type)
            for prem, fwd, strk, years, option_type in zip(
                premium, forward, strike, t, snapshot["option_type"], strict=True
            )
        ]
    )
    points = pd.DataFrame(
        {
            "strike": strike,
            "expiry": snapshot["expiry"].to_numpy(),
            "option_type": snapshot["option_type"].to_numpy(),
            "k": np.log(strike / forward),
            "T": t,
            "w": iv**2 * t,
            "iv": iv,
        }
    )
    return PipelineResult(points=points)
