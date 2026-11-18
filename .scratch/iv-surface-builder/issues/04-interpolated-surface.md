# 04: Multi-expiry InterpolatedSurface

**What to build:** A full surface, not just one smile. The synthetic generator produces several expiries. A common `Surface` interface exposes vectorised `iv(k, T)` and `total_variance(k, T)`. `InterpolatedSurface` builds a grid and spline directly from the (k, T, w) points. The pipeline result includes this surface, and the app adds a 3D σ(k, T) plot and the ATM term structure (σ at k = 0 against T).

**Blocked by:** 01

**Status:** resolved

- [x] The synthetic generator supports multiple expiries.
- [x] The `Surface` interface defines `iv(k, T)` and `total_variance(k, T)`, both accepting arrays.
- [x] `InterpolatedSurface` reproduces the input points within tolerance, and gives sensible values between them.
- [x] The pipeline result includes the interpolated surface.
- [x] A pipeline test on a multi-expiry synthetic chain recovers the known IVs at off-grid (k, T) points within tolerance.
- [x] The app shows a 3D σ(k, T) plot and an ATM term-structure chart.
