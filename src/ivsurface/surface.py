"""Implied volatility surfaces in (k, T): log-moneyness k = ln(K/F) and time to expiry T in years."""

from collections.abc import Sequence
from typing import NamedTuple, Protocol

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike, NDArray
from scipy.interpolate import CubicSpline

from ivsurface.svi import SVIParams


class Surface(Protocol):
    expiries: NDArray[np.float64]
    """The times to expiry (years, ascending) of the quoted slices the surface was built from."""

    def total_variance(self, k: ArrayLike, t: ArrayLike) -> NDArray[np.float64]:
        """w(k, T) = sigma(k, T)^2 * T, elementwise over broadcast k and t."""
        ...

    def iv(self, k: ArrayLike, t: ArrayLike) -> NDArray[np.float64]:
        """sigma(k, T), elementwise over broadcast k and t."""
        ...


class _SlicedSurface:
    """Shared across-expiry rules for surfaces built from one smile per quoted expiry.

    - Along T, w is linear between neighbouring expiries at fixed k (so if no two slices cross,
      the surface is free of calendar arbitrage).
    - Before the first and after the last expiry, sigma is held flat at that slice's value.

    Subclasses set ``expiries`` (ascending) and say how to evaluate each slice in k.
    """

    expiries: NDArray[np.float64]

    def _slice_total_variance(self, j: int, k: NDArray[np.float64]) -> NDArray[np.float64]:
        raise NotImplementedError

    def total_variance(self, k: ArrayLike, t: ArrayLike) -> NDArray[np.float64]:
        k_arr, t_arr = np.broadcast_arrays(np.asarray(k, dtype=float), np.asarray(t, dtype=float))
        k_flat, t_flat = k_arr.ravel(), t_arr.ravel()
        # w of every slice at every query k: shape (n_slices, n_queries).
        w_slices = np.array([self._slice_total_variance(j, k_flat) for j in range(len(self.expiries))])
        expiries = self.expiries

        def flat_vol_from(j: int) -> NDArray[np.float64]:
            """Hold slice j's sigma fixed and scale its total variance to the query T."""
            return w_slices[j] * t_flat / expiries[j]

        if len(expiries) == 1:
            return flat_vol_from(0).reshape(k_arr.shape)

        # Index of the slice at or below each query T, clipped so [i, i+1] is a valid pair.
        i = np.clip(np.searchsorted(expiries, t_flat, side="right") - 1, 0, len(expiries) - 2)
        cols = np.arange(len(k_flat))
        t0, t1 = expiries[i], expiries[i + 1]
        w0, w1 = w_slices[i, cols], w_slices[i + 1, cols]
        w = w0 + (w1 - w0) * (t_flat - t0) / (t1 - t0)

        w = np.where(t_flat < expiries[0], flat_vol_from(0), w)
        w = np.where(t_flat > expiries[-1], flat_vol_from(-1), w)
        return w.reshape(k_arr.shape)

    def iv(self, k: ArrayLike, t: ArrayLike) -> NDArray[np.float64]:
        t_arr = np.asarray(t, dtype=float)
        return np.sqrt(self.total_variance(k, t_arr) / t_arr)


class _SplineSlice(NamedTuple):
    """One expiry's smile: a spline of total variance in k, valid on [k_min, k_max]."""

    t: float
    k_min: float
    k_max: float
    w: CubicSpline


class InterpolatedSurface(_SlicedSurface):
    """The baseline surface: interpolate the quoted points directly, with no model.

    Along k, each expiry's slice is a natural cubic spline through its total variances. Outside a
    slice's quoted k range, w is held flat at the nearest quoted value. Across T, see
    ``_SlicedSurface``.

    The spline can wiggle between quotes and the slices can cross, so this surface is free to
    contain static arbitrage. That is the point of it: it is the baseline SVI improves on.
    """

    def __init__(self, points: pd.DataFrame) -> None:
        """Build from rows with columns k, T, w. Expiries with fewer than two distinct k are skipped."""
        slices: list[_SplineSlice] = []
        for t in np.unique(points["T"].to_numpy(dtype=float)):
            group = points.loc[points["T"] == t].sort_values("k").drop_duplicates("k")
            if len(group) < 2:
                continue
            k = group["k"].to_numpy(dtype=float)
            spline = CubicSpline(k, group["w"].to_numpy(dtype=float), bc_type="natural")
            slices.append(_SplineSlice(float(t), float(k[0]), float(k[-1]), spline))
        if not slices:
            raise ValueError("an interpolated surface needs at least one expiry with two quoted strikes")
        self._slices = slices
        self.expiries = np.array([s.t for s in slices])

    def _slice_total_variance(self, j: int, k: NDArray[np.float64]) -> NDArray[np.float64]:
        s = self._slices[j]
        return s.w(np.clip(k, s.k_min, s.k_max))


class SVISurface(_SlicedSurface):
    """One raw SVI smile per expiry; SVI's own wings extrapolate in k. Across T, see
    ``_SlicedSurface``."""

    def __init__(self, slices: Sequence[tuple[float, SVIParams]]) -> None:
        """Build from (T, params) pairs, one per expiry."""
        if not slices:
            raise ValueError("an SVI surface needs at least one fitted expiry")
        ordered = sorted(slices, key=lambda s: s[0])
        self._params = [p for _, p in ordered]
        self.expiries = np.array([t for t, _ in ordered], dtype=float)

    def _slice_total_variance(self, j: int, k: NDArray[np.float64]) -> NDArray[np.float64]:
        return self._params[j].total_variance(k)
