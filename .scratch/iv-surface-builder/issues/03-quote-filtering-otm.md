# 03: Quote filtering and OTM selection

**What to build:** The pipeline uses only clean, OTM quotes, priced at mid: puts below the forward and calls above it. Zero-bid quotes, wide-spread quotes and short expiries are filtered out, using thresholds from a filter config. Every rejected quote stays in the points table with a reason code. Synthetic chains gain realistic bid/ask spreads and noise. The app adds filter controls and a summary of rejected quotes.

**Blocked by:** 01

**Status:** resolved

- [x] The synthetic generator supports bid/ask spreads and price noise.
- [x] Only OTM options are inverted, and ITM quotes get a reason code saying so.
- [x] Mid price, (bid + ask) / 2, is used for inversion.
- [x] Zero-bid quotes, quotes over the maximum relative spread, and expiries under the minimum days (default about 2) are rejected, each with its own reason code.
- [x] All thresholds are configurable through a filter config passed to the pipeline.
- [x] The points table includes the spread for each quote.
- [x] Pipeline tests on synthetic chains with planted bad quotes confirm the right reason codes.
- [x] The app shows filter controls and counts of rejected quotes by reason.
