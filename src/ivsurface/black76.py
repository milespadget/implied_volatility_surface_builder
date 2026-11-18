"""Black-76 pricing on a forward with zero rates (forward-dollar premiums)."""

import math
from collections.abc import Callable
from enum import StrEnum
from typing import Literal, NamedTuple

import numpy as np
from scipy.optimize import brentq

OptionType = Literal["call", "put"]

_EPS = np.finfo(np.float64).eps

SIGMA_MIN = 1e-8
SIGMA_MAX = 20.0
"""The search range for implied vol. Anything outside it is reported as no convergence."""


class Reason(StrEnum):
    """Why an implied vol was (or was not) produced for a quote."""

    OK = "ok"
    BELOW_INTRINSIC = "below_intrinsic"
    ABOVE_UPPER_BOUND = "above_upper_bound"
    NO_CONVERGENCE = "no_convergence"


class IVResult(NamedTuple):
    iv: float
    """The implied vol, or NaN when ``reason`` is not OK."""
    reason: Reason

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
) -> IVResult:
    """Invert Black-76 for sigma.

    Prices outside the no-arbitrage bounds are rejected up front: with r = 0 a call lies in
    (max(F - K, 0), F) and a put in (max(K - F, 0), K), and only those open intervals map to a
    positive, finite sigma.
    """
    intrinsic = max(forward - strike, 0.0) if option_type == "call" else max(strike - forward, 0.0)
    upper = forward if option_type == "call" else strike
    if not premium > intrinsic:
        return IVResult(math.nan, Reason.BELOW_INTRINSIC)
    if not premium < upper:
        return IVResult(math.nan, Reason.ABOVE_UPPER_BOUND)

    def excess(sigma: float) -> float:
        return price(forward, strike, t, sigma, option_type) - premium

    # Price is increasing in sigma, so [lo, hi] always brackets the root and every Newton
    # iterate tightens one side of it.
    lo, hi = SIGMA_MIN, SIGMA_MAX
    # Manaster-Koehler start: the inflection point of price(sigma), from which Newton
    # converges monotonically. ATM it is 0, so floor it at a small positive vol.
    sigma = min(max(math.sqrt(2.0 * abs(math.log(forward / strike)) / t), 1e-3), SIGMA_MAX)
    for _ in range(max_iter):
        diff = excess(sigma)
        if diff > 0.0:
            hi = sigma
        else:
            lo = sigma
        v = vega(forward, strike, t, sigma)
        if not v > 0.0:
            break  # vega underflowed: Newton cannot take a step
        step = diff / v
        sigma -= step
        # Stop on the size of the sigma step, not the price residual: an absolute price
        # tolerance is meaningless when the premium (or its time value) is tiny.
        if abs(step) < tol * max(sigma, 1.0):
            return IVResult(sigma, Reason.OK)
        if not lo < sigma < hi:
            break  # Newton escaped the bracket
    return _brent_fallback(excess, lo, hi, tol)


def _brent_fallback(excess: Callable[[float], float], lo: float, hi: float, tol: float) -> IVResult:
    """Slow but sure: Brent's method on whatever bracket Newton left behind."""
    if not (excess(lo) < 0.0 < excess(hi)):
        return IVResult(math.nan, Reason.NO_CONVERGENCE)
    sigma, info = brentq(excess, lo, hi, xtol=tol * 1e-2, rtol=np.float64(4 * _EPS), full_output=True)
    if not info.converged:
        return IVResult(math.nan, Reason.NO_CONVERGENCE)
    return IVResult(float(sigma), Reason.OK)
