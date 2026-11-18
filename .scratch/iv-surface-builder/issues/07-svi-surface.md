# 07: SVI surface

**What to build:** The smooth, arbitrage-aware surface. A raw SVI slice (a, b, ρ, m, σ) is fitted to each expiry's total variance:
- weighted least squares with `scipy.optimize.least_squares`, using 1/spread weights;
- bounds b ≥ 0, |ρ| < 1 and σ > 0, plus a check that minimum variance a + bσ√(1−ρ²) ≥ 0;
- a heuristic initial guess with a few random restarts.

`SVISurface` implements the `Surface` interface. It interpolates linearly in w at fixed k between expiries, and extrapolates flat in σ beyond the first and last expiries. The pipeline returns the SVI parameters for each expiry, the SVI surface and its arbitrage report. The app overlays the SVI curve on each smile and compares arbitrage between the interpolated and SVI surfaces.

**Blocked by:** 03, 05, 06

**Status:** resolved

- [x] Synthetic chains generated from known SVI parameters (with noise) give recovered parameters and IVs within tolerance (pipeline seam).
- [x] Every fitted slice satisfies the parameter bounds and has non-negative minimum variance.
- [x] `SVISurface` is linear in total variance across T, and flat in σ outside the quoted expiry range.
- [x] The pipeline result includes the SVI parameters for each expiry, the SVI surface, and the SVI surface's arbitrage report.
- [x] On the real fixtures, the SVI surface has no more arbitrage violations than the interpolated surface.
- [x] The app smiles show market IV, mark_iv, the interpolated curve and the SVI curve, and the arbitrage panel compares the two surfaces.

## Comments

- **From the review of tickets 02–04:** the points table has `relative_spread` = (ask − bid) / mid, not an absolute spread. That suits 1/spread weights, because it is scale-free in total variance. But the synthetic oracle defaults to `relative_spread=0.0`, which makes 1/spread infinite. Either floor the weight or give the SVI oracle tests a non-zero spread. `Surface` now declares `expiries`, so `SVISurface` must expose it too.
- **Resolved (ticket 07):** on the real BTC fixture, SVI has 0 butterfly and 0 calendar violations, against 175 and 0 for the interpolated surface. Its median IV misfit is 0.0007. Not enforced: Roger Lee's wing bound b(1+|ρ|) ≤ 2. The 309-day slice has b(1−ρ) ≈ 3.1, which only affects extrapolation beyond the quoted strikes, where nothing is checked. SVI skips expiries with fewer than 5 usable quotes, and the app then falls back to the interpolated surface.
