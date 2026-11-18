# 05: Arbitrage diagnostics

**What to build:** Detect static arbitrage in any `Surface`. Butterfly arbitrage is checked on each slice using Durrleman's g(k) < 0. Calendar arbitrage is checked wherever w(k, T) decreases as T increases at fixed k. The pipeline returns an arbitrage report for each surface, listing violation locations and magnitudes, and the app adds an arbitrage panel.

**Blocked by:** 04

**Status:** resolved

- [x] The butterfly check evaluates Durrleman's g(k) on each expiry slice and reports where g(k) < 0, with its magnitude.
- [x] The calendar check reports (k, T) regions where w decreases in T, with their magnitude.
- [x] The checks work against the `Surface` interface, not a specific implementation.
- [x] The pipeline result includes an arbitrage report for the interpolated surface.
- [x] Synthetic surfaces built with butterfly or calendar violations are flagged, and clean synthetic surfaces are not (pipeline seam).
- [x] The app shows an arbitrage panel summarising the violations.

## Comments

- Counts are grid points in violation, not merged regions. `ArbitrageReport.share(kind)` gives the fraction of checked points in violation, so ticket 07 can compare surfaces independently of grid size. The report also carries the g(k) curves it checked.
