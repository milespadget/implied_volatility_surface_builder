"""Quote screening: decide which snapshot rows are fit to invert, and why the rest are not."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.typing import NDArray

SHORT_EXPIRY = "short_expiry"
ITM = "itm"
ZERO_BID = "zero_bid"
WIDE_SPREAD = "wide_spread"


@dataclass(frozen=True)
class FilterConfig:
    min_bid: float = 0.0
    """A quote needs a bid strictly above this (in units of the underlying) to be used."""
    max_relative_spread: float = 0.5
    """Largest (ask - bid) / mid accepted."""
    min_days_to_expiry: float = 2.0
    """Expiries closer than this (in calendar days) are dropped: near-expiry quotes are noise."""


def relative_spread(bid: NDArray[np.float64], ask: NDArray[np.float64]) -> NDArray[np.float64]:
    """(ask - bid) / mid, NaN where there is no market at all."""
    with np.errstate(divide="ignore", invalid="ignore"):
        return (ask - bid) / (0.5 * (ask + bid))


def screen(
    snapshot: pd.DataFrame, t: NDArray[np.float64], config: FilterConfig = FilterConfig()
) -> list[str | None]:
    """One entry per snapshot row: a rejection reason, or None if the quote should be inverted.

    ``t`` is each row's time to expiry in years. Checks run in a fixed order and the first
    failure wins: short expiry, then ITM, then zero bid, then wide spread.

    Only OTM quotes are used: puts struck below the forward and calls at or above it. ITM
    options are dominated by intrinsic value, so their time value (and hence their implied
    vol) is poorly determined; their OTM counterparts carry the same information.
    """
    strike = snapshot["strike"].to_numpy(dtype=float)
    forward = snapshot["underlying_price"].to_numpy(dtype=float)
    is_call = (snapshot["option_type"] == "call").to_numpy()
    bid = snapshot["bid"].to_numpy(dtype=float)
    ask = snapshot["ask"].to_numpy(dtype=float)

    days = t * 365.0
    otm = np.where(is_call, strike >= forward, strike < forward)
    spread = relative_spread(bid, ask)

    checks = [
        (days < config.min_days_to_expiry, SHORT_EXPIRY),
        (~otm, ITM),
        (~(bid > config.min_bid), ZERO_BID),
        (~(spread <= config.max_relative_spread), WIDE_SPREAD),
    ]
    reasons: list[str | None] = [None] * len(snapshot)
    for failed, reason in reversed(checks):  # earlier checks overwrite later ones
        for i in np.flatnonzero(failed):
            reasons[i] = reason
    return reasons
