# Spec: Implied Volatility Surface Builder

Status: ready-for-agent

## Problem Statement

I want a portfolio project that shows I understand options pricing and volatility modelling, rigorously and from first principles. Option prices on their own don't tell you much. The useful information is the implied volatility the market is pricing in, across strikes and expiries. Getting it means working backwards from each option price to its implied vol, cleaning the noisy quotes, and then building a smooth, arbitrage-aware surface from the resulting scatter of points. Off-the-shelf tools hide all of this. I want to build it myself, check it against a known truth and against an exchange's own numbers, and present it so a recruiter or interviewer can click through it.

## Solution

A Python library plus a Streamlit app that builds implied volatility surfaces from Deribit BTC (and ETH) option chains:

- Fetch an option chain from Deribit's free public API and save it as a reproducible snapshot.
- Invert Black-76 for each out-of-the-money (OTM) quote to get its implied vol. The forward comes from Deribit, and every rejected quote gets an explicit reason.
- Build two surfaces from the resulting points:
  - a simple interpolated surface, as the baseline;
  - an SVI surface: one SVI slice fitted per expiry, interpolated across expiries.
- Detect butterfly and calendar arbitrage in both surfaces, showing why raw interpolation is weak and SVI is better.
- Verify everything against a synthetic oracle (chains generated from known SVI parameters) and against Deribit's own `mark_iv`.
- Present the results in a Streamlit app: a 3D surface, smiles by expiry, the ATM term structure and an arbitrage panel.

## User Stories

1. As a project author, I want to fetch the current BTC option chain from Deribit's public API, so that I can build a surface from real market data without paying for data.
2. As a project author, I want the underlying to be a parameter, so that I can build ETH surfaces with no code changes.
3. As a project author, I want each fetched chain saved as a timestamped snapshot file, so that every result is reproducible.
4. As a project author, I want each snapshot row to record strike, expiry, call or put, bid, ask, mark price, Deribit mark_iv, underlying price and snapshot time, so that the pipeline has everything it needs without calling the network again.
5. As a project author, I want one or two small real snapshots committed as fixtures, so that tests and demos run offline.
6. As a project author, I want all other snapshots kept out of version control, so that the repo stays small.
7. As a project author, I want to load any saved snapshot by underlying and timestamp, so that I can compare surfaces over time.
8. As a quant learner, I want a Black-76 pricer for calls and puts on a forward, so that I can price European options in forward terms.
9. As a quant learner, I want Black-76 vega, so that the IV solver can take Newton steps.
10. As a quant learner, I want to invert Black-76 with Newton-Raphson, so that most quotes converge quickly.
11. As a quant learner, I want the solver to fall back to Brent's method when vega is tiny or Newton leaves its bracket, so that deep OTM and short-dated quotes still solve reliably.
12. As a quant learner, I want the solver to reject prices outside the no-arbitrage bounds (below intrinsic, or above the forward or strike bound) with an explicit reason, so that I never report a meaningless IV.
13. As a quant learner, I want a solver that fails to converge to return NaN with a "no convergence" reason, so that failures are visible rather than silent.
14. As a project author, I want Deribit's BTC-denominated premiums converted to forward-dollar terms (BTC price × F), so that they're consistent with Black-76 on F.
15. As a project author, I want the forward for each expiry taken from Deribit's underlying_price, so that I don't have to derive it myself.
16. As a project author, I want the risk-free rate set to zero, so that the forward-measure set-up stays simple and correct for this market.
17. As a quant learner, I want time to expiry measured in calendar seconds from the snapshot to the 08:00 UTC expiry, divided by the seconds in a 365-day year, so that the clock matches a market that trades around the clock.
18. As a quant learner, I want only OTM options used (puts below the forward, calls above it), so that I invert the liquid, time-value-dominated side of each strike.
19. As a quant learner, I want mid prices used for inversion, so that the IV isn't biased towards either side of the spread.
20. As a quant learner, I want quotes with a zero bid dropped, so that untradeable quotes don't distort the smile.
21. As a quant learner, I want quotes with very wide relative spreads dropped, so that unreliable mids are left out.
22. As a quant learner, I want expiries under about two days dropped, so that near-expiry noise doesn't dominate.
23. As a project author, I want every filter threshold to be configurable, so that I can explore how the filters affect the surface.
24. As a project author, I want every rejected quote kept in the results with a reason code, so that I can see exactly what was dropped and why.
25. As a quant learner, I want each surviving quote expressed as log-moneyness k = ln(K/F), time T and total variance w = σ²T, so that the data model fits SVI and the arbitrage checks directly.
26. As a quant learner, I want an interpolated surface built directly from the (k, T, w) points, so that I have a simple baseline.
27. As a quant learner, I want a raw SVI slice (a, b, ρ, m, σ) fitted to each expiry, so that each smile is smooth and extrapolates sensibly.
28. As a quant learner, I want the SVI fit to be weighted least squares on total variance, with weights of 1/spread, so that tight quotes count more.
29. As a quant learner, I want the SVI fit constrained so that b ≥ 0, |ρ| < 1, σ > 0 and minimum variance ≥ 0, so that every fitted slice is valid.
30. As a quant learner, I want the SVI fit seeded from a heuristic guess with a few random restarts, so that it doesn't get stuck in bad local minima.
31. As a quant learner, I want the SVI surface interpolated linearly in total variance at fixed k between expiries, so that slices that don't cross can't introduce calendar arbitrage.
32. As a quant learner, I want the SVI surface extrapolated flat in σ before the first and after the last expiry, so that queries outside the quoted range return sensible values.
33. As a library user, I want both surfaces to share one interface exposing iv(k, T) and total_variance(k, T), so that the app and the arbitrage checks treat them the same way.
34. As a quant learner, I want butterfly arbitrage detected on each slice using Durrleman's g(k) < 0, so that I can see where a smile implies a negative density.
35. As a quant learner, I want calendar arbitrage detected wherever w(k, T) decreases as T increases, so that I can see where slices cross.
36. As a quant learner, I want an arbitrage report for each surface, listing where violations occur and how severe they are, so that I can compare the interpolated and SVI surfaces.
37. As a project author, I want a single pipeline entry point that turns a snapshot into per-quote points, both surfaces and the arbitrage reports, so that the app and the tests use the same path.
38. As a project author, I want to generate synthetic chains from known SVI parameters for each expiry, with bid/ask noise, so that I can test the pipeline against a known truth.
39. As a project author, I want the synthetic generator to produce data in the same schema as a real snapshot, so that it goes through the exact same pipeline.
40. As a project author, I want my computed IVs compared against Deribit's mark_iv, so that I have a real-world check on the solver and the forward handling.
41. As a viewer of the app, I want to pick a saved snapshot, so that I can explore different market states.
42. As a viewer of the app, I want a button that fetches a fresh snapshot, so that I can see the current market.
43. As a viewer of the app, I want a 3D plot of σ(k, T), so that I can see the whole surface at once.
44. As a viewer of the app, I want a smile chart for each expiry, showing market IV points, Deribit mark_iv, the interpolated curve and the SVI curve, so that I can judge how good the fit is.
45. As a viewer of the app, I want a short note explaining why my IVs differ slightly from mark_iv (mids versus mark prices), so that the small gaps aren't mistaken for bugs.
46. As a viewer of the app, I want an ATM term structure chart (σ at k = 0 against T), so that I can see how vol changes with expiry.
47. As a viewer of the app, I want an arbitrage panel comparing violations in the interpolated and SVI surfaces, so that the case for SVI is visible.
48. As a viewer of the app, I want to see how many quotes were rejected and why, so that I understand how much data the surface rests on.
49. As a viewer of the app, I want to adjust the filter thresholds, so that I can see how they change the surface.
50. As a recruiter or interviewer, I want to click through a running app rather than read a notebook, so that I can judge the work quickly.

## Implementation Decisions

- **Stack:** Python, using numpy, scipy and pandas, tested with pytest and packaged with uv. There is one library package and a separate Streamlit app that depends on it.
- **Market model:** Deribit options are European, and Black-76 prices them on the forward F. F for each expiry is Deribit's `underlying_price`. Premiums are converted from BTC to forward-dollar terms by multiplying by F, and r = 0.
- **Time convention:** T is the seconds from the snapshot timestamp to expiry (08:00 UTC on the expiry date), divided by the seconds in a 365-day year.
- **Coordinates:** points and surfaces use log-moneyness k = ln(K/F) and time T, storing total variance w = σ²T. σ is derived for display.

**Modules**
- **black76:** price, vega and implied-vol inversion. Inversion uses Newton-Raphson with vega and falls back to Brent's method within the no-arbitrage price bounds. It returns an IV, or NaN with a reason code.
- **data:** the Deribit public-API client (no API key), and snapshot save and load in Parquet.
  - Snapshots are named by underlying and UTC timestamp.
  - Each row is an instrument with these columns: strike, expiry, option type, bid, ask, mark, mark_iv, underlying_price, snapshot time.
- **chain:** filtering and OTM selection.
  - Takes a snapshot table plus a filter config: minimum bid, maximum relative spread and minimum days to expiry, all configurable.
  - Returns a points table with one row per input quote: k, T, w, IV, spread and reason code. A reason code of "ok" marks the rows that are used.
- **svi:** the raw SVI function and the per-expiry fitter. The fitter uses `scipy.optimize.least_squares` with bounds, 1/spread weights and heuristic initialisation with random restarts.
- **surface:** a common `Surface` interface with two implementations.
  - **Interface:** `iv(k, T)` and `total_variance(k, T)`, both vectorised.
  - **InterpolatedSurface:** a grid and spline built directly from the points.
  - **SVISurface:** the fitted slices, interpolated linearly in w at fixed k across T, and extrapolated flat in σ beyond the first and last expiries.
- **arbitrage:** given any `Surface` and its expiries, produces a report.
  - Butterfly arbitrage uses Durrleman's g(k) on each slice.
  - Calendar arbitrage checks that w is non-decreasing in T at fixed k.
  - The report lists violation locations and magnitudes.
- **synthetic:** generates snapshot-schema chains from per-expiry SVI parameters, a forward and a noise and spread model. This is the test oracle.
- **Pipeline entry point:** snapshot table plus config in; a result object out, holding the points table, both surfaces, the SVI parameters for each expiry and the arbitrage report for each surface. The app and the tests both call this one function.
- **App:** a Streamlit front end.
  - Controls: a snapshot picker, a fetch-fresh-snapshot button and filter controls.
  - Views: the 3D surface, smiles by expiry (market IV, mark_iv, the interpolated curve and the SVI curve), the ATM term structure, the arbitrage panel and the rejected-quote summary.
- **Storage:** one or two small real snapshots are committed as test fixtures. All other snapshots are gitignored.

## Testing Decisions

- **What a good test is:** tests only check external behaviour at public seams, meaning inputs in and observable outputs out. They never check internal helpers, optimiser internals or intermediate data structures. A refactor that keeps behaviour the same should break no tests.
- **Seam 1 (main): the pipeline entry point.** Most tests go through it.
  - **Synthetic oracle:** chains generated from known SVI parameters must give recovered SVI parameters and IVs within tolerance.
  - **Reason codes:** bad quotes (zero bid, wide spread, short expiry, price below intrinsic) must come back with the right reason codes.
  - **Arbitrage flags:** surfaces built to contain butterfly or calendar arbitrage must be flagged, and clean ones must not.
  - **Real fixtures:** the committed snapshots must produce IVs close to Deribit's mark_iv within a tolerance, and SVI must produce no more arbitrage violations than the interpolated surface.
  - **Indirect coverage:** filtering, SVI fitting, surface interpolation and arbitrage detection are tested only through this seam, with no unit tests of their own.
- **Seam 2: the black76 public functions.**
  - Round-trip tests: price with a known σ, invert, and recover σ across a grid of k, T and σ.
  - Edge cases: deep OTM, very short expiry, tiny vega, and prices below intrinsic or above the upper bound, which must give NaN with the right reason.
- **Seam 3: the Deribit fetch boundary.** The HTTP layer is replaced with a recorded JSON response, and tests assert that the resulting snapshot table has the agreed schema and correct unit handling. Tests never make live network calls.
- **App:** a single smoke test checks that the app imports and runs against a fixture snapshot. There are no UI behaviour tests.
- **Prior art:** none. This is a greenfield repo, and these tests set the pattern.

## Out of Scope

- SSVI, or any surface-wide parametrisation with built-in no-arbitrage constraints. This is a stretch goal for later.
- Calibrating stochastic-vol models such as Heston or SABR.
- Heston-generated synthetic data.
- The Zeller-Mitchell quasi-explicit SVI fit.
- Deriving the forward independently from put-call parity. This could be a later cross-check.
- Equity or index options (SPX and others), American exercise, dividends, and FX.
- Jäckel's "Let's Be Rational" IV algorithm.
- Live streaming or automatic snapshot scheduling.
- Production hardening, packaging for other people, and performance at scale.

## Further Notes

- The project tells one story: start with raw inversion and a naïve interpolated surface, show that it produces arbitrage, then show SVI fixing most of it. The app should make that comparison obvious.
- Expect small gaps between our IVs and Deribit's mark_iv, because we invert mid prices and Deribit inverts mark prices. The app should explain this.
- The build order and the split into issues will be decided later.
