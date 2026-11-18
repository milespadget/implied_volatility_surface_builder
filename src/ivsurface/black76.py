"""Black-76 pricing on a forward with zero rates (forward-dollar premiums)."""

import math
from typing import Literal

OptionType = Literal["call", "put"]

_SQRT2 = math.sqrt(2.0)
_INV_SQRT_2PI = 1.0 / math.sqrt(2.0 * math.pi)


def _norm_cdf(x: float) -> float:
    return 0.5 * math.erfc(-x / _SQRT2)


def _norm_pdf(x: float) -> float:
    return _INV_SQRT_2PI * math.exp(-0.5 * x * x)


def _d1_d2(forward: float, strike: float, t: float, sigma: float) -> tuple[float, float]:
    total_sd = sigma * math.sqrt(t)
    d1 = (math.log(forward / strike) + 0.5 * total_sd**2) / total_sd
    return d1, d1 - total_sd


def price(forward: float, strike: float, t: float, sigma: float, option_type: OptionType) -> float:
    """Undiscounted Black-76 premium of a European option on the forward."""
    d1, d2 = _d1_d2(forward, strike, t, sigma)
    if option_type == "call":
        return forward * _norm_cdf(d1) - strike * _norm_cdf(d2)
    return strike * _norm_cdf(-d2) - forward * _norm_cdf(-d1)


def vega(forward: float, strike: float, t: float, sigma: float) -> float:
    """Sensitivity of the premium to sigma (same for calls and puts)."""
    d1, _ = _d1_d2(forward, strike, t, sigma)
    return forward * math.sqrt(t) * _norm_pdf(d1)


def implied_vol(
    premium: float,
    forward: float,
    strike: float,
    t: float,
    option_type: OptionType,
    *,
    tol: float = 1e-10,
    max_iter: int = 100,
) -> float:
    """Invert Black-76 for sigma with Newton-Raphson. Returns NaN if it fails to converge."""
    # Manaster-Koehler start: the inflection point of price(sigma), from which Newton
    # converges monotonically. ATM it is 0, so floor it at a small positive vol.
    sigma = max(math.sqrt(2.0 * abs(math.log(forward / strike)) / t), 1e-3)
    for _ in range(max_iter):
        v = vega(forward, strike, t, sigma)
        if v <= 0.0:
            return math.nan
        step = (price(forward, strike, t, sigma, option_type) - premium) / v
        sigma -= step
        if not sigma > 0.0:
            return math.nan
        # Stop on the size of the sigma step, not the price residual: an absolute price
        # tolerance is meaningless when the premium (or its time value) is tiny.
        if abs(step) < tol * max(sigma, 1.0):
            return sigma
    return math.nan
