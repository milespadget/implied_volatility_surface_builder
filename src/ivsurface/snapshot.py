"""The snapshot schema: one row per option instrument at one point in time.

Units follow Deribit's conventions so a snapshot is a faithful record of the raw quotes:

- ``bid``, ``ask``, ``mark`` are premiums in units of the underlying (e.g. BTC).
- ``underlying_price`` is the forward F for that instrument's expiry, in USD.
- ``mark_iv`` is a decimal (0.55 means 55%).
- ``expiry`` and ``snapshot_time`` are timezone-aware UTC timestamps.
"""

import numpy as np
from numpy.typing import NDArray

COLUMNS = [
    "underlying",
    "strike",
    "expiry",
    "option_type",
    "bid",
    "ask",
    "mark",
    "mark_iv",
    "underlying_price",
    "snapshot_time",
]


def to_forward_dollars[T: (float, NDArray[np.float64])](premium_in_underlying: T, forward: T) -> T:
    """Deribit premium (units of the underlying) -> forward-dollar premium for Black-76 on F."""
    return premium_in_underlying * forward


def to_underlying_units[T: (float, NDArray[np.float64])](premium_in_forward_dollars: T, forward: T) -> T:
    """Forward-dollar premium -> Deribit premium (units of the underlying)."""
    return premium_in_forward_dollars / forward
