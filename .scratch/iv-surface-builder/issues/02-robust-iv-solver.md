# 02: Robust IV solver with reason codes

**What to build:** IV inversion that never returns a meaningless number. When vega is tiny, or a Newton step leaves the bracket, the solver falls back to Brent's method. Prices outside the Black-76 no-arbitrage bounds are rejected. Every failure gives NaN with a reason code, which shows up in the pipeline's points table.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Deep OTM, very short expiry and tiny-vega cases converge, via the Brent fallback (Black-76 seam tests).
- [ ] A price below intrinsic gives NaN with a "below intrinsic" reason.
- [ ] A price above the upper bound gives NaN with an "above upper bound" reason.
- [ ] Non-convergence gives NaN with a "no convergence" reason.
- [ ] Successfully inverted quotes have a reason code of "ok".
- [ ] The pipeline's points table includes the reason code for every input quote.
