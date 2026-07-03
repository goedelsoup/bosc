# Wilmington Low-Flow Screen — Ungaged Todd Fork 7Q10 via Drainage-Area Ratio

The **defining Wilmington receiving-water problem** (#516 / #886): the Wilmington Air Park and the
City WWTP both discharge into a reach with **no active USGS gage**, so the at-site 7Q10 that the
Tier-0 surface screen needs cannot be read directly off a gage. This document pins the
**drainage-area-ratio (DAR) method** used to bracket that ungaged reach, and names the primary
instruments that must supply the drainage areas before the derived 7Q10 is trusted. Status **as of
2026-07-03**.

**Discipline:** the DAR *method* below is standard USGS practice `[reference]`; the specific
**drainage areas** it multiplies are marked `[open]` until pulled from USGS site metadata /
StreamStats. Until each DA is cited, the Todd Fork 7Q10 is a **documented method awaiting inputs,
not a finding.** No drainage area or 7Q10 figure here is fabricated.

## The two receiving waters

- **Wilmington Air Park (ILN)** — the single-tenant Amazon Air / ATSG cargo hub. Its stormwater /
  any process discharge drains to **Todd Fork → Little Miami River** (HUC-8 05090202). `[reference]`
- **City of Wilmington WWTP** — outfall 001 to **Lytle Creek** at RM 6.83 (Lytle Creek → Todd Fork
  → Little Miami). NPDES **OH0028134 / 1PD00013\*QD**, design flow 3.0 MGD (PTI #1543170 expansion
  to 4.5 MGD, new limits effective 2026-03-01). `[verified — Ohio EPA NPDES fact sheet 1PD00013.fs,
  2023-05-19]` (already carried on the `SiteProfile.plant_receiving` for `wilmington-wwtp`.)

Both receiving waters sit on **Todd Fork or a Todd Fork tributary** — the ungaged reach this screen
is about.

## Why the reach is ungaged

Todd Fork has **no active USGS daily-discharge gage**. The historical gage on the creek
(**03244000**) was **discontinued**, and Clinton County has no active continuous-record gage. So the
at-site 7Q10 cannot be computed by LP3 over a gage record the way Milford or Oldtown can. Rather than
proxy Todd Fork to the far-downstream Little Miami mainstem (which would badly **overstate** the
dilution available at the Air Park / WWTP outfalls), the reach is **bracketed** and interpolated.

## The bracket (added to the basin table, #516)

`watermark.hydrology.basin._MAINSTEM_GAGES` now carries **both** Little Miami mainstem brackets, so
`derive-low-flows` produces an LP3 7Q10 for each on the next connectivity-permitting run:

| role | gage | station | drainage area |
|---|---|---|---|
| downstream integrator (below the Todd Fork confluence) | `03245500` | Little Miami River at Milford OH | 1664 mi² `[reference]` |
| upstream reach (above the Todd Fork confluence) | `03240000` | Little Miami River near Oldtown OH | `[open]` — pull from NWIS site metadata |
| **ungaged target** | (`03244000`, discontinued) | **Todd Fork** near mouth / at the Air Park reach | `[open]` — pull from USGS StreamStats |

Oldtown carries a non-colliding alias (`little miami river near oldtown`) so it does not capture
ECHO's bare `little miami river` (aliased to Milford) — Todd Fork dischargers stay `no_7q10` under
the ECHO basin-screen; this at-site DAR value is a **manual receiving-water characterization**, not
an auto-applied screen denominator.

## The drainage-area-ratio adjustment

Standard USGS transfer of a low-flow statistic from a gaged reach to an ungaged one on the same
stream system `[reference]`:

```
Q7Q10(ungaged) = Q7Q10(gaged) × ( DA(ungaged) / DA(gaged) )^b
```

- `DA` = contributing drainage area.
- `b` = a transfer exponent. The simple DAR uses **b = 1.0**; for Ohio low flows a regional exponent
  from the USGS Ohio low-flow report (Koltun) may be substituted. `[reference]` The choice of `b`
  and its source must be recorded when the DAs are filled in.
- Todd Fork's mouth DA is much smaller than the Little Miami mainstem at either bracket, so the DAR
  correctly shrinks the at-site 7Q10 well below the Milford value — the whole point of not proxying
  to the mainstem.

The interpolation is **bounded by the two brackets**: the Oldtown 7Q10 (upstream, Todd-Fork-free)
and the Milford 7Q10 (downstream, includes Todd Fork) frame the plausible range; the DAR sets the
point estimate inside it.

## Scenic-river overlay `[reference]`

The Little Miami is a **National & State Scenic River** — the same anti-degradation overlay as Xenia
upstream. A scenic-river designation typically **raises the in-stream passby minimum** protecting the
reach, so the `SiteProfile` passby fields (`passby_primary_cfs` / `passby_secondary_cfs`, currently
`0.0 [open]`) should be revisited against the Ohio EPA anti-degradation record once the DAR 7Q10 is
in hand. Until cited, this stays **to-verify.**

## Instruments to pull (priority order)

1. **USGS StreamStats (Ohio)** — delineate Todd Fork at the Air Park reach and at its mouth; read the
   contributing drainage area. Fills the `[open]` DA for the ungaged target.
2. **USGS NWIS site metadata** — `03240000` (Oldtown) and the discontinued `03244000` (Todd Fork)
   station drainage areas + period of record. Fills the Oldtown DA and confirms the historical
   Todd Fork gage's DA for a cross-check.
3. **USGS Ohio low-flow report (Koltun)** — regional 7Q10 transfer exponent `b` for the DAR, if the
   simple `b = 1.0` is not used.
4. **Ohio EPA NPDES fact sheet 1PD00013.fs** (already cited for the WWTP) — confirm the Lytle Creek
   design-flow assimilative basis and any stated receiving-water 7Q10 for a sanity check against the
   DAR result.
5. **Ohio EPA anti-degradation / scenic-river record** — the in-stream passby minimum for the Little
   Miami reach.

## Sources

- Basin gage table (Milford + Oldtown brackets): `src/watermark/hydrology/basin.py` `_MAINSTEM_GAGES`
- WWTP receiving water + NPDES: `SiteProfile` `plant_receiving["wilmington-wwtp"]`
  (`src/watermark/sites/_profiles.py`)
- Derived 7Q10 table (Milford committed; Oldtown populates on the next run):
  `data/reference/hydrology/low-flow-7q10.derived.yaml`
- Wilmington onboarding self-research pass (the ungaged-Todd-Fork finding):
  `data/research/onboard-wilmington-*/` (see `data/extracted/wilmington/ONBOARDING.md`)
