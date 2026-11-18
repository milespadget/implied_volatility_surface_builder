"""Static-arbitrage diagnostics for any Surface.

- **Butterfly** arbitrage on a slice means the smile implies a negative risk-neutral density.
  Durrleman's condition: the density is non-negative iff g(k) >= 0, where, with w = w(k, T)
  and primes for d/dk,

      g(k) = (1 - k w' / (2 w))^2 - (w'^2 / 4) (1/w + 1/4) + w'' / 2.

- **Calendar** arbitrage means total variance falls as expiry lengthens at fixed k: a longer
  option would be worth less than a shorter one.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from ivsurface.surface import Surface

VIOLATION_COLUMNS = ["kind", "k", "T", "magnitude"]

GRID_POINTS = 201
"""k points checked per slice (or per pair of slices, for calendar arbitrage)."""
FD_STEP = 1e-4
"""Finite-difference step in k for w' and w''."""
TOLERANCE = 1e-6
"""Violations smaller than this are treated as numerical noise."""


class ViolationKind(StrEnum):
    BUTTERFLY = "butterfly"
    CALENDAR = "calendar"


@dataclass(frozen=True)
class SliceG:
    """Durrleman's g on one slice, over exactly the k grid the butterfly check used."""

    t: float
    k: NDArray[np.float64]
    g: NDArray[np.float64]


@dataclass(frozen=True)
class ArbitrageReport:
    violations: pd.DataFrame
    """One row per grid point in violation: kind (a ViolationKind), k, T, magnitude.

    For butterfly rows, magnitude is -g(k) > 0 and T is the slice's expiry. For calendar rows,
    magnitude is the fall in total variance and T is the later of the two expiries.
    """
    butterfly_curves: list[SliceG]
    """g(k) for every slice checked, so a plot shows exactly what was counted."""
    points_checked: dict[ViolationKind, int]
    """How many grid points each check evaluated."""

    @property
    def is_free(self) -> bool:
        return len(self.violations) == 0

    def count(self, kind: ViolationKind) -> int:
        """Grid points in violation of this kind."""
        return int(np.sum(self.violations["kind"].to_numpy() == kind))

    def share(self, kind: ViolationKind) -> float:
        """Fraction of checked grid points in violation: comparable across surfaces and grids."""
        checked = self.points_checked[kind]
        return self.count(kind) / checked if checked else 0.0


def check(surface: Surface, k_ranges: Sequence[tuple[float, float]]) -> ArbitrageReport:
    """Check ``surface`` for butterfly and calendar arbitrage.

    ``k_ranges`` gives, for each of ``surface.expiries``, the (k_min, k_max) over which that slice
    is backed by quotes. Only that range is checked: outside it a surface is extrapolating.

    The calendar check only compares neighbouring quoted expiries, so it requires the surface to
    be linear in total variance between them (then w is non-decreasing in T everywhere iff it is
    non-decreasing from each quoted expiry to the next).
    """
    rows: list[dict[str, object]] = []
    curves: list[SliceG] = []
    for t, (k_min, k_max) in zip(surface.expiries, k_ranges, strict=True):
        # Stay inside the quoted range by more than the stencil reaches, so g never differences
        # across the surface's extrapolation.
        k = np.linspace(k_min + 2 * FD_STEP, k_max - 2 * FD_STEP, GRID_POINTS)
        g = durrleman_g(surface, k, float(t))
        curves.append(SliceG(float(t), k, g))
        bad = g < -TOLERANCE
        for k_bad, g_bad in zip(k[bad], g[bad], strict=True):
            rows.append({"kind": ViolationKind.BUTTERFLY, "k": k_bad, "T": float(t), "magnitude": -g_bad})

    expiries = surface.expiries
    calendar_checked = 0
    for i in range(len(expiries) - 1):
        k_min = max(k_ranges[i][0], k_ranges[i + 1][0])
        k_max = min(k_ranges[i][1], k_ranges[i + 1][1])
        if k_min >= k_max:
            continue  # the two slices share no quoted k
        k = np.linspace(k_min, k_max, GRID_POINTS)
        calendar_checked += len(k)
        earlier, later = float(expiries[i]), float(expiries[i + 1])
        fall = surface.total_variance(k, np.full_like(k, earlier)) - surface.total_variance(k, np.full_like(k, later))
        bad = fall > TOLERANCE
        for k_bad, fall_bad in zip(k[bad], fall[bad], strict=True):
            rows.append({"kind": ViolationKind.CALENDAR, "k": k_bad, "T": later, "magnitude": fall_bad})

    return ArbitrageReport(
        violations=pd.DataFrame(rows, columns=VIOLATION_COLUMNS),
        butterfly_curves=curves,
        points_checked={
            ViolationKind.BUTTERFLY: GRID_POINTS * len(curves),
            ViolationKind.CALENDAR: calendar_checked,
        },
    )


def durrleman_g(surface: Surface, k: NDArray[np.float64], t: float) -> NDArray[np.float64]:
    """Durrleman's g(k) on the slice at expiry ``t``; negative where the density is negative."""
    t_arr = np.full_like(k, t)
    w = surface.total_variance(k, t_arr)
    w_up = surface.total_variance(k + FD_STEP, t_arr)
    w_down = surface.total_variance(k - FD_STEP, t_arr)
    dw = (w_up - w_down) / (2 * FD_STEP)
    d2w = (w_up - 2 * w + w_down) / FD_STEP**2
    return (1 - k * dw / (2 * w)) ** 2 - dw**2 / 4 * (1 / w + 0.25) + d2w / 2
