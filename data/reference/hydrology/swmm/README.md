# Tier-1 EPA SWMM input decks

The four `.inp` models the Tier-1 run is computed from, committed for **chain of custody**:
the reviewed result in [`../tier1-swmm.yaml`](../tier1-swmm.yaml) records each deck's
`sha256`, so a reader can re-run the exact inputs that produced the reported numbers rather
than trusting the summary.

| Deck | What it models |
|---|---|
| `tier1-pre.inp` | Pre-development campus subcatchment → outfall (the peak the post case must not exceed). |
| `tier1-post.inp` | Post-development (paved) subcatchment → outfall, **undetained**. |
| `tier1-detention.inp` | The post case routed through a storage node + bottom orifice — the basin `run_tier1` bisects to hold the release to the pre-development peak. |
| `tier1-sanitary.inp` | A sanitary junction carrying dry-weather base flow + RDII (an R-T-K unit hydrograph) to the WWTP outfall — the wet-weather surcharge check. |

## Source

**Generated, not authored** — `watermark.hydrology.swmm.inp` builds the text and
`watermark.hydrology.tier1` grounds it. Regenerate with:

```sh
watermark tier1 --write
```

They are **not** hand-editable: the next `--write` reverts any edit, and the recorded
`sha256` would no longer match. Change the builder, not the deck.

The design rainfall in each `[TIMESERIES]` block is the NRCS Type-II 24-hour distribution at
its published 6-minute resolution (`watermark.hydrology.solver.rainfall`, NEH-630 Ch. 4
§630.0407), scaled to the cited NOAA Atlas-14 corridor depth in
[`../atlas14-corridor-ddf.yaml`](../atlas14-corridor-ddf.yaml).

## Discipline & gaps

- **`source: derived`.** Only the footprint area, the storm depth, and the plant design flows
  are document/connector-sourced. The drainage network these decks describe is **not in the
  record** — widths, slopes, Manning's *n*, infiltration, RDII R-T-K, and the basin geometry
  are stated screening **assumptions**, and the single-subcatchment representation is a
  screening idealisation of a real piped network.
- Subcatchment surface slope and pervious depression storage are grounded off the graded rim
  relief where a site supplies it (WS-25 / #1625), not left at the generic 1.0 % / 0.05 in.
- The decks are **Lima-shaped today**: `run_tier1` builds them for the active site's
  footprint, but only Lima has the committed footprint + sanitary basis they need.
- **Tier-1 is not Tier-0.** These are the real engine's inputs; the fast, auditable SCS
  screening chain lives in `watermark.hydrology.solver` and does not read them. Neither is a
  calibrated HEC-RAS model or a permit determination.
- **Regenerating requires a working engine.** `pyswmm` must load — on Apple Silicon that can
  need an ad-hoc `codesign -s - -f` of the vendored `swmm-toolkit` native libraries. Without
  it `watermark tier1` reports the engine unavailable and writes nothing, so a stale deck is
  possible; the recorded `sha256` in `../tier1-swmm.yaml` is what ties a result to its inputs.
