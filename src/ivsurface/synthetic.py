"""Synthetic option chains with a known true volatility, used as a test oracle."""

from collections.abc import Callable, Sequence
from datetime import datetime

import math

import numpy as np
import pandas as pd

from ivsurface import black76
from ivsurface.snapshot import COLUMNS, to_underlying_units
from ivsurface.time import year_fraction


VolFunction = Callable[[float, float], float]
"""A true implied vol as a function of log-moneyness k = ln(K/F) and time to expiry T."""


def option_chain(
    *,
    forward: float,
    vol: float | VolFunction,
    strikes: Sequence[float],
    expiries: Sequence[datetime],
    snapshot_time: datetime,
    underlying: str = "BTC",
    relative_spread: float = 0.0,
    noise: float = 0.0,
    seed: int | None = None,
) -> pd.DataFrame:
    """A chain with a call and a put per strike per expiry, priced at a known true vol.

    ``vol`` is either a flat vol or a function sigma(k, T).

    ``relative_spread`` sets (ask - bid) / mid. ``noise`` perturbs each mid by a lognormal
    factor exp(noise * Z), so a quote's mid sits roughly ``noise`` (relatively) off the true
    price while staying positive; ``mark`` is the noise-free model price.
    """
    rng = np.random.default_rng(seed)
    vol_at: VolFunction = vol if callable(vol) else (lambda k, t: vol)
    rows = []
    for expiry, strike in ((e, s) for e in expiries for s in strikes):
        t = year_fraction(snapshot_time, expiry)
        sigma = vol_at(math.log(strike / forward), t)
        for option_type in ("call", "put"):
            premium = to_underlying_units(black76.price(forward, strike, t, sigma, option_type), forward)
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
                    "mark_iv": sigma,
                    "underlying_price": forward,
                    "snapshot_time": pd.Timestamp(snapshot_time),
                }
            )
    return pd.DataFrame(rows, columns=COLUMNS)
