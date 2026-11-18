"""Synthetic option chains with a known true volatility, used as a test oracle."""

from collections.abc import Sequence
from datetime import datetime

import math

import numpy as np
import pandas as pd

from ivsurface import black76
from ivsurface.snapshot import COLUMNS, to_underlying_units
from ivsurface.time import year_fraction


def flat_vol_chain(
    *,
    forward: float,
    vol: float,
    strikes: Sequence[float],
    expiry: datetime,
    snapshot_time: datetime,
    underlying: str = "BTC",
    relative_spread: float = 0.0,
    noise: float = 0.0,
    seed: int | None = None,
) -> pd.DataFrame:
    """A single-expiry chain (a call and a put per strike) priced at a flat vol.

    ``relative_spread`` sets (ask - bid) / mid. ``noise`` perturbs each mid by a lognormal
    factor exp(noise * Z), so a quote's mid sits roughly ``noise`` (relatively) off the true
    price while staying positive; ``mark`` is the noise-free model price.
    """
    rng = np.random.default_rng(seed)
    t = year_fraction(snapshot_time, expiry)
    rows = []
    for strike in strikes:
        for option_type in ("call", "put"):
            premium = to_underlying_units(black76.price(forward, strike, t, vol, option_type), forward)
            mid = premium * math.exp(noise * rng.standard_normal())
            rows.append(
                {
                    "underlying": underlying,
                    "strike": float(strike),
                    "expiry": pd.Timestamp(expiry),
                    "option_type": option_type,
                    "bid": mid * (1.0 - relative_spread / 2.0),
                    "ask": mid * (1.0 + relative_spread / 2.0),
                    "mark": premium,
                    "mark_iv": vol,
                    "underlying_price": forward,
                    "snapshot_time": pd.Timestamp(snapshot_time),
                }
            )
    return pd.DataFrame(rows, columns=COLUMNS)
