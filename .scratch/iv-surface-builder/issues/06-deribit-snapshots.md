# 06: Deribit fetch, snapshots and real data in the app

**What to build:** Real market data. A client for Deribit's public API (no key) fetches the full option chain for an underlying (BTC by default, ETH via a parameter). Each expiry's forward F is taken from `underlying_price`, and premiums are converted from BTC to forward-dollar terms (BTC price × F). The chain is saved as a timestamped Parquet snapshot. The app gets a snapshot picker, a fetch-fresh-snapshot button, a Deribit mark_iv overlay on each smile, and a short note on why mid-based IVs differ slightly from mark_iv.

**Blocked by:** 02, 03

**Status:** ready-for-agent

- [ ] The Deribit client fetches the chain for a given underlying and produces a table in the agreed snapshot schema.
- [ ] Premiums are converted BTC → forward-dollar using each instrument's underlying_price as F.
- [ ] Snapshots are saved and loaded as Parquet, named by underlying and UTC timestamp.
- [ ] One or two small real snapshots are committed as test fixtures, and all other snapshots are gitignored.
- [ ] The fetch-seam test uses a recorded JSON response (no live network) and checks the schema and units.
- [ ] A pipeline test on the real fixtures shows "ok" IVs within tolerance of mark_iv.
- [ ] The app has a snapshot picker and a fetch button, overlays mark_iv on the smiles, and explains the mid-versus-mark gap.

## Comments

- **From ticket 01 (snapshot schema decisions):** the schema in the `snapshot` module also has an `underlying` column. Premiums (`bid`/`ask`/`mark`) stay in units of the underlying, exactly as Deribit quotes them, and the pipeline converts them to forward dollars with the shared unit helpers. `mark_iv` is stored as a **decimal**, but Deribit returns it in percent, so the client must divide by 100, and the fetch-seam test should check that. The `.gitignore` entry for `data/snapshots/` is still to do in this ticket.
