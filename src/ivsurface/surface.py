"""Implied volatility surfaces in (k, T): log-moneyness k = ln(K/F) and time to expiry T in years."""

from typing import Protocol

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike, NDArray
from scipy.interpolate import CubicSpline


class Surface(Protocol):
    def total_variance(self, k: ArrayLike, t: ArrayLike) -> NDArray[np.float64]:
        """w(k, T) = sigma(k, T)^2 * T, elementwise over broadcast k and t."""
        ...

    def iv(self, k: ArrayLike, t: ArrayLike) -> NDArray[np.float64]:
        """sigma(k, T), elementwise over broadcast k and t."""
        ...


class InterpolatedSurface:
    """The baseline surface: interpolate the quoted points directly, with no model.

    - Along k, each expiry's slice is a natural cubic spline through its total variances.
      Outside a slice's quoted k range, w is held flat at the nearest quoted value.
    - Along T, w is linear between neighbouring expiries at fixed k.
    - Before the first and after the last expiry, sigma is held flat at that slice's value.

    The spline can wiggle between quotes and the slices can cross, so this surface is free to
    contain static arbitrage. That is the point of it: it is the baseline SVI improves on.
    """

    def __init__(self, points: pd.DataFrame) -> None:
        """Build from rows with columns k, T, w. Each expiry needs at least two distinct k."""
        slices = []
        for t in np.unique(points["T"].to_numpy(dtype=float)):
            group = points.loc[points["T"] == t].sort_values("k").drop_duplicates("k")
            if len(group) < 2:
                continue
            k = group["k"].to_numpy(dtype=float)
            slices.append((float(t), k[0], k[-1], CubicSpline(k, group["w"].to_numpy(dtype=float), bc_type="natural")))
        if not slices:
            raise ValueError("an interpolated surface needs at least one expiry with two quoted strikes")
        self.expiries = np.array([s[0] for s in slices])
        """The time to expiry, in years, of each slice the surface is built from."""
        self._slices = slices

    def _slice_variances(self, k: NDArray[np.float64]) -> NDArray[np.float64]:
        """w of every slice at every k: shape (n_slices, len(k))."""
        return np.array([spline(np.clip(k, k_lo, k_hi)) for _, k_lo, k_hi, spline in self._slices])

    def total_variance(self, k: ArrayLike, t: ArrayLike) -> NDArray[np.float64]:
        k_arr, t_arr = np.broadcast_arrays(np.asarray(k, dtype=float), np.asarray(t, dtype=float))
        shape = k_arr.shape
        k_flat, t_flat = k_arr.ravel(), t_arr.ravel()
        w_slices = self._slice_variances(k_flat)
        expiries = self.expiries
        cols = np.arange(len(k_flat))

        if len(expiries) == 1:
            w = w_slices[0] * t_flat / expiries[0]
            return w.reshape(shape)

        # Index of the slice at or below each query T, clipped so [i, i+1] is a valid pair.
        i = np.clip(np.searchsorted(expiries, t_flat, side="right") - 1, 0, len(expiries) - 2)
        t0, t1 = expiries[i], expiries[i + 1]
        w0, w1 = w_slices[i, cols], w_slices[i + 1, cols]
        w = w0 + (w1 - w0) * (t_flat - t0) / (t1 - t0)

        # Flat in sigma outside the quoted expiries: w scales with T at the end slice's vol.
        before, after = t_flat < expiries[0], t_flat > expiries[-1]
        w = np.where(before, w_slices[0] * t_flat / expiries[0], w)
        w = np.where(after, w_slices[-1] * t_flat / expiries[-1], w)
        return w.reshape(shape)

    def iv(self, k: ArrayLike, t: ArrayLike) -> NDArray[np.float64]:
        t_arr = np.asarray(t, dtype=float)
        return np.sqrt(self.total_variance(k, t_arr) / t_arr)
