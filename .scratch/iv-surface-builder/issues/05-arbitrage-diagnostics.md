# 05: Arbitrage diagnostics

**What to build:** Detect static arbitrage in any `Surface`. Butterfly arbitrage is checked on each slice using Durrleman's g(k) < 0. Calendar arbitrage is checked wherever w(k, T) decreases as T increases at fixed k. The pipeline returns an arbitrage report for each surface, listing violation locations and magnitudes, and the app adds an arbitrage panel.

**Blocked by:** 04

**Status:** ready-for-agent

- [ ] The butterfly check evaluates Durrleman's g(k) on each expiry slice and reports where g(k) < 0, with its magnitude.
- [ ] The calendar check reports (k, T) regions where w decreases in T, with their magnitude.
- [ ] The checks work against the `Surface` interface, not a specific implementation.
- [ ] The pipeline result includes an arbitrage report for the interpolated surface.
- [ ] Synthetic surfaces built with butterfly or calendar violations are flagged, and clean synthetic surfaces are not (pipeline seam).
- [ ] The app shows an arbitrage panel summarising the violations.
