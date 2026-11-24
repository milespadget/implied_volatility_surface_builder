# 10: 3D surface boundary that only widens with T

**What to build:** A 3D surface whose drawn k range never narrows as expiry lengthens, so its edges are smooth and have no notches. This is presentation only: the surfaces and the pipeline do not change.

At the moment each row's k range is the quoted range, interpolated between expiries. The quoted range does not always grow with T. On the real BTC fixture the 8.5d expiry is quoted up to k = +0.28 but the 15.5d expiry only up to +0.24. So the call-side edge steps in and then out again, and the surface has a notch.

Fix: make the boundary only widen with T. Going from short expiries to long, take the running maximum of the call-side edge (highest quoted k) and the running minimum of the put-side edge (lowest quoted k). Then interpolate between expiries as now. The 15.5d row then runs out to +0.28, not +0.24. That is a small extrapolation of the SVI smile beyond its quoted strikes. It is sensible because quoted strike ranges grow with expiry anyway. The edge becomes smooth, and no quote falls into a notch.

This relaxes one rule from ticket 09: "the surface is never drawn beyond an expiry's quoted strikes". The new rule is that a row may reach out to the widest quoted edge of any shorter expiry, and no further. The 2nd–98th percentile k trim from ticket 09 still applies after the envelope.

**Blocked by:** 09

**Status:** ready-for-agent

- [ ] Along the rows, in order of T, the drawn lowest k never increases and the drawn highest k never decreases.
- [ ] At each quoted expiry, the drawn range is the running envelope: from the lowest quoted k of that expiry or any shorter one, to the highest quoted k of that expiry or any shorter one. The 2nd–98th percentile trim still applies. On the BTC fixture the 15.5d row reaches +0.28.
- [ ] No row is drawn beyond the envelope (no extrapolation past the widest quoted edge so far).
- [ ] Every plotted quote still lies inside the drawn region, and every quoted expiry is still a row.
- [ ] The ticket 09 test that the surface is never drawn beyond an expiry's own quoted strikes is replaced by the envelope test. The other app smoke tests still pass. No pipeline or surface behaviour changes.
