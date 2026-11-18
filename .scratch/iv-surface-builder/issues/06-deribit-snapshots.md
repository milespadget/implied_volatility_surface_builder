# 06: Deribit fetch, snapshots and real data in the app

**What to build:** Real market data. A client for Deribit's public API (no key) fetches the full option chain for an underlying (BTC by default, ETH via a parameter). Each expiry's forward F is taken from `underlying_price`, and premiums are converted from BTC to forward-dollar terms (BTC price × F). The chain is saved as a timestamped Parquet snapshot. The app gets a snapshot picker, a fetch-fresh-snapshot button, a Deribit mark_iv overlay on each smile, and a short note on why mid-based IVs differ slightly from mark_iv.

**Blocked by:** 02, 03

**Status:** resolved

- [x] The Deribit client fetches the chain for a given underlying and produces a table in the agreed snapshot schema.
- [x] Premiums are converted BTC → forward-dollar using each instrument's underlying_price as F.
- [x] Snapshots are saved and loaded as Parquet, named by underlying and UTC timestamp.
- [x] One or two small real snapshots are committed as test fixtures, and all other snapshots are gitignored.
- [x] The fetch-seam test uses a recorded JSON response (no live network) and checks the schema and units.
- [x] A pipeline test on the real fixtures shows "ok" IVs within tolerance of mark_iv.
- [x] The app has a snapshot picker and a fetch button, overlays mark_iv on the smiles, and explains the mid-versus-mark gap.

## Comments

- **From ticket 01 (snapshot schema decisions):** the schema in the `snapshot` module also has an `underlying` column. Premiums (`bid`/`ask`/`mark`) stay in units of the underlying, exactly as Deribit quotes them, and the pipeline converts them to forward dollars with the shared unit helpers. `mark_iv` is stored as a **decimal**, but Deribit returns it in percent, so the client must divide by 100, and the fetch-seam test should check that. The `.gitignore` entry for `data/snapshots/` is still to do in this ticket.
- **From the review of tickets 02–04:** `FilterConfig.max_relative_spread` defaults to 0.5. Real Deribit wing quotes are often more than 100% of mid (a 1-tick bid with an ask several ticks higher), so this default may reject most of the wings. Re-check the default against the committed fixtures. Also, a put struck exactly at the forward is dropped with reason `atm_duplicate`.
- **Resolved (ticket 06):** `max_relative_spread` stays at 0.5. On the committed BTC fixture it drops 33 of the 378 otherwise usable OTM quotes, all of them thin wing markets; 1.0 would drop none. Snapshots carry one `snapshot_time`, the earliest Deribit `creation_timestamp`. Per-instrument times split each expiry into many T values. Snapshots load by path, through `list_snapshots`; there is no lookup by (underlying, time) yet.
