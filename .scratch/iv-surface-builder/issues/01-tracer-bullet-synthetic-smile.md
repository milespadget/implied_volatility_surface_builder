# 01: Tracer bullet: synthetic chain → IV points → smile in the app

**What to build:** The thinnest working path through the whole system. A synthetic single-expiry chain, in the snapshot schema, goes through the pipeline entry point. Each quote is inverted to an implied vol with Black-76 (basic Newton-Raphson using vega). The pipeline returns a points table (k = ln(K/F), T, w = σ²T, IV), and a minimal Streamlit page plots the resulting smile. This also sets up the uv project with numpy, scipy, pandas, pytest and Streamlit.

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] The uv project installs, and pytest runs.
- [x] Black-76 prices calls and puts on a forward with r = 0, and exposes vega.
- [x] Newton-Raphson IV inversion recovers σ in round-trip tests across a grid of k, T and σ (Black-76 seam).
- [x] The synthetic generator produces a single-expiry chain in the snapshot schema (strike, expiry, option type, bid, ask, mark, mark_iv, underlying_price, snapshot time) from a known vol.
- [x] T is the calendar seconds from the snapshot to the 08:00 UTC expiry, divided by the seconds in a 365-day year.
- [x] The pipeline entry point takes a snapshot table and returns a result whose points table holds k, T, w and IV.
- [x] A pipeline test on synthetic data recovers the known vol within tolerance.
- [x] The Streamlit page plots the smile (IV against k) for a synthetic chain.
- [x] A smoke test confirms the app imports and runs.

## Comments

- Resolved in commit d736c14.
