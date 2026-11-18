"""Why each quote did or did not become an implied-vol point: one vocabulary for the whole pipeline."""

from enum import StrEnum


class Reason(StrEnum):
    OK = "ok"
    """Inverted successfully; the point is used to build surfaces."""

    # Screening (ivsurface.chain), checked in this order; the first failure wins.
    SHORT_EXPIRY = "short_expiry"
    ITM = "itm"
    ATM_DUPLICATE = "atm_duplicate"
    """A put struck exactly at the forward: the ATM call already carries the same information."""
    ZERO_BID = "zero_bid"
    WIDE_SPREAD = "wide_spread"

    # Inversion (ivsurface.black76).
    BELOW_INTRINSIC = "below_intrinsic"
    ABOVE_UPPER_BOUND = "above_upper_bound"
    NO_CONVERGENCE = "no_convergence"
