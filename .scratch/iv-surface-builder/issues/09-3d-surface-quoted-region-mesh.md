# 09: 3D surface drawn on the quoted region

**What to build:** A 3D surface whose edges follow the quoted strikes smoothly, with enough resolution at short expiries, and with every plotted quote on or near the drawn surface. This is presentation only: the surfaces and the pipeline do not change. Seen on the real BTC snapshot:

- **Jagged edges.** The surface is masked to the quoted region on a rectangular 61 × 60 (k, T) grid. Each grid cell is either fully drawn or blank, so the edge of the quoted region comes out as a staircase. That makes the sawtooth along the left edge and the spikes near the front.
- **Front end too coarse.** The T rows are spaced evenly between the first and last expiry (about 2.5 to 309 days, so roughly 5 days apart). The shortest expiries are only a few days apart, and that is where the smile changes most, so each gets only a row or two. That is why the short-dated region looks spiky.
- **Dots float off the surface.** The k grid is clipped to the 2nd to 98th percentile of k, but the scatter still plots every quote. Wing quotes sit in empty space (k ≈ −1, around 140%). They also stretch the σ axis to 140%, which flattens everything else.

Fixes:

- Give each T row its own k range, from k_min(T) to k_max(T): each expiry's quoted range, interpolated between expiries as the mask does now. Pass x as a 2D array to `go.Surface` instead of masking a meshgrid. Plotly accepts 2D x and y, so the edge becomes a smooth curve. This fixes the jagged edges and most of the front-end spikes.
- Space the T rows by √T or log T, and add each quoted expiry as a row, so the short-dated end gets its resolution.
- Plot only the quotes that fall inside the drawn region, or extend the drawn region to cover them. Either way the σ axis shrinks back to roughly 50 to 90%.

**Blocked by:** 08

**Status:** resolved

- [x] The 3D surface has no blank cells inside the quoted region: each T row runs from that row's k_min(T) to k_max(T), so the edges are smooth curves, not staircases.
- [x] Every quoted expiry is a row of the mesh, and the rows are denser at short T than at long T.
- [x] Every quote plotted on the 3D chart lies inside the drawn (k, T) region. On the real BTC snapshot, the σ axis no longer reaches 140%.
- [x] The surface is still never drawn outside the quoted strikes at any expiry (no wing extrapolation, as in the earlier spike fix).
- [x] The existing app smoke tests still pass. No pipeline or surface behaviour changes.

## Comments

- **Resolved (ticket 09):** the mesh has one row per quoted expiry inside the main surface's expiry range, including expiries SVI skipped for having too few quotes. There are 38 more rows evenly spaced in √T, and each row has 61 points across its own k range. The drawn range is every quoted expiry's k range, interpolated in T and trimmed to the 2nd–98th percentile of all quotes' k. Only quotes inside it are plotted, and the caption says how many are left out.
- **Decision: the drawn region is trimmed, not just the dots.** Drawing every quoted wing would bring back the 140% quote (k ≈ −1.09 at 30.6d on the 24 Nov snapshot), and the σ axis would stretch again. So the long-dated far wings are left out of the chart, though they are still quoted and fitted.
- **σ axis:** about 40–75% on the committed fixture. About 45–110% on the 24 Nov snapshot: the 140% quote is gone, but quotes inside the band reach about 112% (k −0.40 at 9.6d), and those are real.
- **Known edge cases, not handled:** an expiry whose whole quoted range lies outside the band collapses to a zero-width row. A surface with a single expiry has one row, so Plotly draws no surface (as before this ticket).
