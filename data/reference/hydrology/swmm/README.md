# Tier-1 EPA SWMM input decks

The six `.inp` models the Tier-1 run is computed from, committed for **chain of custody**:
the reviewed result in [`../tier1-swmm.yaml`](../tier1-swmm.yaml) records each deck's
`sha256`, so a reader can re-run the exact inputs that produced the reported numbers rather
than trusting the summary.

| Deck | What it models |
|---|---|
| `tier1-pre.inp` | Pre-development campus subcatchment → outfall (the peak the post case must not exceed). |
| `tier1-post.inp` | Post-development **as permitted** → outfall, **undetained**: `%Imperv` is the footprint's declared permanently-impervious acreage over the measured parcel (WS-14 / #1614). |
| `tier1-full-buildout.inp` | The same subcatchment at the blanket near-impervious **bound** (the whole parcel paved), undetained — the peer of the Tier-0 screen's `full_buildout_peak_cfs`. |
| `tier1-detention.inp` | The as-permitted case routed through a storage node + bottom orifice — the basin `run_tier1` bisects to hold the release to the pre-development peak. **This is the sizing the permitted project needs.** |
| `tier1-detention-full-buildout.inp` | The same bisection against the full-buildout bound, held to the same pre-development peak — the storage a built-out parcel would need. |
| `tier1-sanitary.inp` | A sanitary junction carrying dry-weather base flow + RDII (an R-T-K unit hydrograph) to the WWTP outfall — the wet-weather surcharge check. |

**The as-permitted and full-buildout decks describe different projects, not two estimates of
one.** Read the deck name before quoting a peak or a storage volume: the Tier-1 escalation
used to run only the blanket value and call it "post-development", which put it at 90 %
impervious against the Tier-0 screen's ~34 % ASWCD-declared composite and sized the reported
basin against the case the SW1225 permit application does not describe.

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

- **`source: derived`.** Only the footprint area, the declared impervious acreage, the storm
  depth, and the plant design flows are document/connector-sourced. The drainage network these
  decks describe is **not in the record** — widths, slopes, Manning's *n*, infiltration, RDII
  R-T-K, the full-buildout imperviousness, and the basin geometry are stated screening
  **assumptions**, and the single-subcatchment representation is a screening idealisation of a
  real piped network.
- **The as-permitted deck is lumped, not split.** SWMM routes the impervious and pervious
  sub-areas of a subcatchment separately, so the declared impervious share is honoured — but
  one subcatchment carries a single pervious cover, so the Tier-0 screen's finer
  developed-pervious vs. undeveloped-cropland split (`stormwater._post_cover_parts`) is not
  reproduced here, and the graded slope is applied across the whole parcel including the
  acreage nobody touched.
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
