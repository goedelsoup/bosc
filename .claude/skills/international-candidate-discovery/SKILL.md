---
name: international-candidate-discovery
description: Use when discovering or interpreting data-center candidates OUTSIDE the US records channel — imagery-led or open-register-led identification abroad. Trigger on "international data centers", "candidates register", watermark candidates output, Johor/Querétaro/Dublin/Singapore sweeps, PeeringDB or OSM telecom=data_center priors, or any request to find data centers where no permit/deed record exists. The inverse of data-center-sweep, which is records-first and US-only. Defers to evidentiary-discipline for all tagging decisions.
---

# International Candidate Discovery

Methodology for the **imagery-and-open-data-led** identification funnel (epic #1387) — the
inverse direction from [`data-center-sweep`](../data-center-sweep/SKILL.md).

Read that skill first if the target is domestic. It is records-first: a resolution, a deed or a
permit proves the project, and imagery only monitors what the record already pinned. **This skill
is for the case where that channel does not exist.** Abroad there is usually no county recorder to
search, no ECHO, no state EPA e-portal — so discovery has to start from the facility rather than
from the instrument, and everything downstream inherits the weakness of that start.

The output is a **candidates register**, and the word is load-bearing. It is a distinct artifact
class from the domestic discover-and-pin register, it is never merged with one, and it mints no
`SiteProfile` — onboarding a watershed point abroad is a story-driven decision, not a detection.

## The tag discipline (the part that is not negotiable)

| Stage | What grounds it | Tag |
|---|---|---|
| Priors — open registers agree | PeeringDB, OSM, operator disclosure, national registry | `[reference]` |
| Geospatial screening | footprint area, substation proximity, construction change | `[inference]` |
| Vision adjudication | halls, rooftop plant, substation yard, cooling type from chips | `[inference]` |
| — | — | **never `[verified]`** |

**Nothing in this funnel can be `[verified]`.** A register agreeing with another register is us
relaying published claims; a screen or a vision read is us adjudicating. Only an instrument
*about that facility* makes a claim `[verified]`, and by construction none is held. In the code
this is enforced rather than remembered: `Candidate.tag` is a computed field derived from
`DetectionBasis`, no basis maps to `verified`, and a `tag:` hand-edited into the committed YAML is
dropped and recomputed on load.

Note the direction of travel: a claim **drops** from `[reference]` to `[inference]` when we
adjudicate it ourselves. That is not a downgrade in quality, it is a change in whose claim it is.

## The disambiguation analog

The domestic skill's guardrail is *place*: "Sidney, OH ≠ Sidney, NY", confirm the county before
recording. Abroad the coordinates are unambiguous — two registers agreeing on a point is a strong
locational claim.

**The risk moves to attribution.** "Whose is it" is the field most likely to be wrong, and the one
a reader will quote. So:

1. An operator name **must** carry a citation to the source that states it, or the field is
   `[open]`. There is no default that asserts a name.
2. Where independent sources name **different** operators, the entry is **contested** and
   publishes both claims. Do not resolve it because one source seems more authoritative — a
   register disagreement is usually an acquisition or rebrand the two updated at different times,
   and *usually* is not a basis for asserting a name. Contested is not `[open]`: the question was
   answered twice, differently, which is more informative than unanswered.
3. Do not normalize corporate names to make a disagreement go away. Containment after casefolding
   ("Equinix" ≡ "Equinix, Inc.") is as far as it goes; anything fuzzier starts *resolving*
   disputes, and a resolved dispute is invisible.
4. A facility name is not an attribution. PeeringDB carries a Querétaro facility named
   "Equinix MX1/MX2 - **Mexico City**" — the market label is stale, the coordinates are right.

## Corroboration: what agreement is worth

A cluster is **corroborated** when ≥2 *independent* sources place a facility there. Two rows from
the same register are one source, however many there are.

Two rules keep that honest, and the second was learned the hard way:

- **The radius is a stated screening parameter, not a measurement.** The registers geocode
  differently (a supplied street address vs. a mapper's building node), so some tolerance is
  required. Widening it manufactures corroboration by merging distinct neighbours.
- **At most one row per source per cluster.** Distance alone cannot separate genuinely adjacent
  data centers, and data centers are built adjacent to each other — that is what a cluster market
  *is*. Plain proximity clustering merged a Dublin business park into one "candidate" carrying
  five different operators. Each register deduplicates itself at the facility level, so a cluster
  can only ever be "this register's row for X plus that register's row for X".

**Keep the single-source leads.** The coverage gap between the registers is itself a finding:
PeeringDB is structurally blind to single-tenant campuses with no carrier presence — precisely the
class this work cares most about — and OSM coverage varies sharply by country. Johor's ~75 mapped
buildings against 6 interconnection rows is that blind spot made visible, not a data error.

## AOI selection: follow the operators, capability first

AOIs come from where operators and interconnection are, **not** from where water is scarce. This
is a locked decision and an easy one to quietly reverse: if a new AOI's stated basis reads like a
water argument, the driver has drifted. The water thesis survives *inside* the detector, as the
`cooling` field, not as the selector.

Every AOI states its own `selection_basis`, and the register republishes it beside the results.

## Negative results are results

An AOI that was swept and yielded nothing gets a row with its raw per-source counts. Omitting it
would read as "never looked". Same rule as the domestic sweep's "No activity found".

## What the funnel cannot tell you

Two registers agreeing a building exists says **nothing** about its size, IT load, cooling design,
water draw, construction phase, or owner beyond the words one of them wrote down. Those fields do
not exist on the record type, deliberately: a field that exists invites a value, and nothing in
this funnel can source one. A priors-only entry is additionally forbidden from carrying a cooling
type or a scene id — no open register publishes cooling design, and no pixels were read.

## Running it

```
watermark candidate-aois                  # the registered AOIs + why each is swept
watermark candidates --dry-run            # sweep, summarize, write nothing
watermark candidates                      # write the YAML + its generated prose peer
watermark candidates --aoi johor,dublin   # a subset
watermark candidates --offline            # committed fixtures only, never fetch
```

Output: `data/extracted/international/data-center-candidates.<scope>.{yaml,md}`. Both are
**generated** — never hand-edit either; the next run reverts it. Corrections go to the input side
(a new prior source, a corrected AOI, a cited disclosure), not to the artifact.

After regenerating, run `watermark catalog reconcile` + `watermark catalog audit --apply`.

## Where things live

- `watermark.international.model` — the artifact class + the rules above, enforced at the type level
- `watermark.international.aois` — the AOI register and each one's stated selection basis
- `watermark.international.register` — the sweep, the matching, the prose renderer
- `watermark.connectors.priors` — PeeringDB + OSM/Overpass, keyless, fixture-backed
- `/network/candidates` — the published map (network-global route, reference-build feed)
