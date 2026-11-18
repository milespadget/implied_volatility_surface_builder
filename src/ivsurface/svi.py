"""Raw SVI smiles (Gatheral): total variance as a function of log-moneyness on one expiry,

    w(k) = a + b * (rho * (k - m) + sqrt((k - m)^2 + sigma^2)),

with b >= 0, |rho| < 1, sigma > 0. Its minimum, a + b * sigma * sqrt(1 - rho^2), must be >= 0 for
the smile to be a variance at all.

Not enforced: Roger Lee's moment bound on the wing slopes, b * (1 + |rho|) <= 2. It only matters
for extrapolation beyond the quoted strikes, which the arbitrage checks do not cover either.
"""

import math
from typing import NamedTuple

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import least_squares

SPREAD_FLOOR = 0.01
"""Relative spreads below this are floored before weighting, so a zero spread can't dominate."""
RESTARTS = 8
"""Random restarts on top of the heuristic start; the best fit wins."""
RHO_LIMIT = 0.999
"""|rho| is held strictly inside 1: at |rho| = 1 one wing is flat and the fit degenerates."""


class SVIParams(NamedTuple):
    a: float
    b: float
    rho: float
    m: float
    sigma: float

    @property
    def min_variance(self) -> float:
        return self.a + self.b * self.sigma * math.sqrt(1.0 - self.rho**2)

    def total_variance(self, k: ArrayLike) -> NDArray[np.float64]:
        k_arr = np.asarray(k, dtype=float)
        return self.a + self.b * (self.rho * (k_arr - self.m) + np.sqrt((k_arr - self.m) ** 2 + self.sigma**2))


def _from_fit_vector(x: NDArray[np.float64]) -> SVIParams:
    """The fitter works with v = minimum variance in place of a, so v >= 0 is a plain bound."""
    v, b, rho, m, sigma = (float(xi) for xi in x)
    vertex_depth = b * sigma * math.sqrt(1.0 - rho**2)
    params = SVIParams(v - vertex_depth, b, rho, m, sigma)
    if params.min_variance < 0.0:  # only rounding when v sits on its bound of 0
        params = params._replace(a=-vertex_depth)
    return params


def fit_slice(
    k: ArrayLike, w: ArrayLike, relative_spread: ArrayLike, *, seed: int = 0
) -> SVIParams:
    """Weighted least-squares fit of raw SVI to one expiry's (k, w) points.

    Residuals are weighted by 1 / relative spread (floored at SPREAD_FLOOR), so tight markets
    count more. Bounds keep b >= 0, |rho| < 1, sigma > 0 and the minimum variance >= 0.
    """
    k_arr, w_arr = np.asarray(k, dtype=float), np.asarray(w, dtype=float)
    weight = 1.0 / np.maximum(np.asarray(relative_spread, dtype=float), SPREAD_FLOOR)
    weight = weight / weight.mean()

    def residuals(x: NDArray[np.float64]) -> NDArray[np.float64]:
        return weight * (_from_fit_vector(x).total_variance(k_arr) - w_arr)

    k_span = float(k_arr.max() - k_arr.min())
    w_max = float(w_arr.max())
    lower = np.array([0.0, 0.0, -RHO_LIMIT, float(k_arr.min()) - k_span, 1e-4])
    upper = np.array([w_max, 10.0 * w_max / max(k_span, 1e-6) + 1.0, RHO_LIMIT, float(k_arr.max()) + k_span, 2.0 * k_span + 1.0])

    # Heuristic start: the vertex sits near the lowest quote, the wings set b and rho.
    i_min = int(np.argmin(w_arr))
    left, right = _wing_slope(k_arr, w_arr, side=-1), _wing_slope(k_arr, w_arr, side=+1)
    b0 = max((right - left) / 2.0, 1e-4)
    rho0 = float(np.clip((right + left) / (right - left) if right > left else 0.0, -0.9, 0.9))
    starts = [np.array([w_arr[i_min], b0, rho0, k_arr[i_min], max(0.1 * k_span, 1e-3)])]
    rng = np.random.default_rng(seed)
    starts += [rng.uniform(lower, upper) for _ in range(RESTARTS)]

    best = None
    for x0 in starts:
        fit = least_squares(residuals, np.clip(x0, lower, upper), bounds=(lower, upper), x_scale="jac")
        if best is None or fit.cost < best.cost:
            best = fit
    assert best is not None
    return _from_fit_vector(best.x)


def _wing_slope(k: NDArray[np.float64], w: NDArray[np.float64], *, side: int) -> float:
    """dw/dk over the outer third of the quotes on one side (side=-1 left, +1 right)."""
    order = np.argsort(k)
    n = max(len(k) // 3, 2)
    idx = order[:n] if side < 0 else order[-n:]
    if np.ptp(k[idx]) == 0:
        return 0.0
    return float(np.polyfit(k[idx], w[idx], 1)[0])
