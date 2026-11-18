"""Synthetic option chains with a known true volatility, used as a test oracle."""

from collections.abc import Sequence
from datetime import datetime

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
) -> pd.DataFrame:
    """A single-expiry chain (a call and a put per strike) priced at a flat vol, with no spread."""
    t = year_fraction(snapshot_time, expiry)
    rows = []
    for strike in strikes:
        for option_type in ("call", "put"):
            premium = to_underlying_units(black76.price(forward, strike, t, vol, option_type), forward)
            rows.append(
                {
                    "underlying": underlying,
                    "strike": float(strike),
                    "expiry": pd.Timestamp(expiry),
                    "option_type": option_type,
                    "bid": premium,
                    "ask": premium,
                    "mark": premium,
                    "mark_iv": vol,
                    "underlying_price": forward,
                    "snapshot_time": pd.Timestamp(snapshot_time),
                }
            )
    return pd.DataFrame(rows, columns=COLUMNS)
