# 08: App presentation polish

**What to build:** Presentation-only fixes to the app, so its charts read clearly in a demo. The maths, the pipeline and the surfaces stay the same. Only the labels, colours, units and camera change.

- **Smiles chart colours repeat.** Plotly's default palette starts again after a few series. With 8 expiries, 2.7d and 89.7d are both blue, 6.7d and 179.7d are both teal, and 13.7d and 364.7d are both purple. Colour the expiries on one sequential scale (short = light, long = dark), so each colour also tells you the expiry. Another option is a selector that shows one or two expiries at a time.
- **3D surface units do not match.** The σ axis is in percent (60%, 70%, 80%), but the colour bar shows decimals (0.55 to 0.8). Give the colour bar the same `.0%` tick format.
- **3D time axis has no title, and the camera is poor.** Only a stray dot shows under the time ticks. The default camera leaves a lot of empty space and makes the surface look tilted. Set a camera position that shows both the skew (along k) and the term structure (along T).
- **Arbitrage metrics show "↑ 0%" arrows.** `st.metric` treats the violation share as a change, so it draws an up-arrow even at 0%. Show the share as plain text under the count, or turn the delta colouring and arrow off.
- **Smiles caption is wrong on synthetic data.** It always says the open markers are "Deribit's mark IV". On synthetic chains the snapshot's mark_iv is the true σ of the vol function that generated the chain. Make the caption (and the legend name) depend on the data source.
- **Term-structure legend case.** The legend entry "true" is lowercase, but the other entries are capitalised. Capitalise it.

**Blocked by:** 07

**Status:** resolved

- [x] No two expiries in the smiles chart share a colour, and the colour order follows expiry order (or a selector shows only a few expiries at a time).
- [x] The 3D colour bar and the σ axis both show percent.
- [x] The 3D time axis has a visible title, and the default camera shows the skew and the term structure without large empty space.
- [x] The arbitrage metrics show no up/down arrows. The violation share is still visible.
- [x] On synthetic data, the smiles caption and legend call the open markers the true IV. On Deribit snapshots they still call them Deribit's mark IV.
- [x] Every term-structure legend entry is capitalised.
- [x] The existing app smoke tests still pass. No pipeline or surface behaviour changes.

## Comments

- **Resolved (ticket 08):** expiries are coloured on a reversed Viridis scale, sampled from 0.15 to 1 so the shortest expiry is not too pale on white. The fitted curves take their expiry's colour, and so do the Durrleman g(k) curves on the Arbitrage tab, because they had the same repeating-palette problem. The metrics keep the share as grey delta text with `delta_arrow="off"`. The 3D time axis title was already in the figure spec; the new camera, eye (−1.5, −1.5, 0.7), and zero margins bring all three axis titles into view (checked on a rendered PNG). The 3D axis titles now read "log-moneyness k", "days to expiry T" and "implied vol σ". The open-marker legend name only shows on hover, because those traces are hidden from the legend (one legend entry per expiry). The caption names them.
