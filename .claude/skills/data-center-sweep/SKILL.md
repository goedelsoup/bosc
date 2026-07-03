---
name: data-center-sweep
description: Use when running or interpreting a data-center activity sweep for a watershed-point site — hyperscale/cloud campus discovery along I-75, rail corridors, or industrial zones. Trigger on "data center sweep", "corridor sweep", "search for data center", watermark sweep data-centers output, or any request to survey data-center activity in a county. Methodology only; site-specific public records live in data/extracted/<site>/data-centers.md. Defers to evidentiary-discipline for all tagging decisions.
---

# Data-Center Activity Sweep

Methodology for discovering and pinning documented data-center projects at a watershed-point
site. The output is a **discover-and-pin register** — not a prediction, not an assessment.
Every entry must have a citable primary source before appearing in `data/extracted/<site>/data-centers.md`.

## Disambiguation guardrail (run first, always)

Before recording any project, confirm it is physically in the target county/city:

1. Check the street address against the county parcel system or Google Maps.
2. Confirm the city/village name in the resolution, deed, or permit matches the site slug.
3. Do not confuse same-named cities (e.g., "Sidney, OH" ≠ "Sidney, NY"; "Lima, OH" ≠ "Lima, Peru").
4. Adjacent-county data centers (Amazon in Union County, Meta in Licking County) are **not**
   in scope for an Allen County site — they are context, not entries.

If you cannot confirm the county, tag the entry `[open]` and list it under a "Pending
confirmation" subsection, not under a numbered project heading.

## Source priority order

Work through sources in this order. Stop when the question is answered by the primary record.

1. **City/township council resolutions** — CRA agreements, PILOT terms, annexations,
   rezoning ordinances, service contracts. Available via the city's public-agenda portal,
   municipal clerk, or municipal website (e.g., `sidneyoh.com/526`). Tag: `[verified]`.
2. **County recorder / auditor** — deed transfers (grantee name, acreage, price if disclosed),
   parcel ownership, assessed value, transfer history. Tag: `[verified]`.
3. **Ohio Secretary of State** — foreign-corp registration for the operating entity and any
   nominee LLC. Tag: `[verified]` when pulled; `[open]` when not yet pulled.
4. **Ohio EPA eSuite / Air Division** — air PTI applications and approvals (emergency generator
   banks are the primary air-permit trigger for a data center). Tag: `[verified]`.
5. **EPA ECHO** — NPDES stormwater general-permit coverage or individual NPDES permits. Run
   `discover_oepa_permits` for the county first; ECHO for the NPDES search. Tag: `[verified]`.
6. **EIA / utility press releases** — large-load interconnect agreements, rate agreements,
   distribution expansion (the power utility is almost always named in the city resolution).
   Tag: `[verified]` for official filings; `[reference]` for press releases only.
7. **Trade press** (Data Center Dynamics, Baxtel, CleanView, DatacenterHawk) — useful for
   investment figures, MW capacity, timeline. Cross-check against primary sources before using.
   Tag: `[reference]` unless independently verified by a primary source.
8. **Advocacy / watchdog sites** (stopohiodatacenters.org, etc.) — use for leads and internal
   cross-references only. Never cite as a primary source for a figure. Tag: `[reference]`.

## Web sweep query patterns

Run `search_web` with queries of the form:

```
"data center" {city} {state}
"hyperscale" OR "cloud campus" {county} {state}
"data center" {city} "I-75" OR "rail corridor"
"large load" {utility_name} {city}
{city} "PILOT" OR "CRA" OR "tax abatement" "data center"
{city} "council resolution" "data center" site:municipalwebsite.gov
```

Follow up with `fetch_url` on any city/council URL, trade press article, or ECHO query
result that names a specific project — resolution PDFs and council-meeting minutes are the
highest-value primary sources.

## Evidence-tag discipline

Every factual statement in the register requires an evidence tag (from evidentiary-discipline):

| Tag | When to use |
|---|---|
| `[verified]` | Cited primary-source instrument you can produce: resolution, deed, filing, permit, executed contract, official municipal website |
| `[inference]` | Arithmetic from cited inputs (e.g., cfs from MGD); timing or proximity pattern explicitly labeled as inference |
| `[open]` | Not yet found in any public source; marks a gap for follow-up |
| `[reference]` | Secondary or advocacy source — DCD article, trade press, watchdog site; contributes leads, never findings |

**Never** assert a figure as `[verified]` unless you can cite the specific instrument. Prefer
`[open]` over a value you do not have a source for.

## Hydrology-hook template

Every project with a disclosed or estimated water draw gets a "Water / hydrology hook" section
and a "Hydrology screen" section. Fill from public sources; mark unknowns `[open]`.

```
### Water / hydrology hook

- **Max withdrawal:** X.X million gallons per day (Y gpm). [Source: resolution / permit]  [verified/open]
- **Projected cooling-water consumption:** Z million gallons per year (~P GPD average). [verified/open]
  Note: the X.X MGD max is peak withdrawal; Z M gal/yr is projected evaporative consumption.
- **Water source:** [municipal system / groundwater / river intake]. [verified/open]
- **Wastewater:** [description → NPDES permit → receiving water]. [verified/open]
- **Stormwater:** [description]. [verified/open]

### Hydrology screen

- **Receiving water (indirect):** [river] at [gage] — 7Q10 [cfs] (from low-flow-7q10.derived.yaml).  [verified]
- **Abstraction vs. 7Q10:** [peak cfs] peak; [avg cfs] average.
  Net consumptive draw is [X]% of 7Q10 — [flag or pass]. [inference]
- **Effluent path:** all process water returns via [NPDES permit ID] (design [Q] MGD, actual [Q] MGD
  [year] DMR). [open/verified]
```

Leave the Hydrology screen as `[open]` if water draw is not publicly disclosed; do not invent figures.

## Register format

```markdown
# {City} / {County} — Data-Center Activity Register

Discover-and-pin register for the {site} onboarding — the **{corridor}** sweep required by
#{issue}. Status **as of {date}**. Tags are BOSC evidentiary discipline: `[verified]` = cited
public source, `[inference]`, `[open]`, `[reference]`. **Nothing here is in the BOSC corpus
yet** — this records the *verified public record* and the specific primary instruments to *pull*.
Every figure is cited; none is fabricated. Do not bridge the Lima/Allen County graph onto
{county} — there is no evidentiary link.

## Disambiguation guardrail

[Confirm the county and city for every entry.]

## 1 — {Operator} / {Project codename}

[Operator, location, investment, power, jobs, timeline — all cited and tagged.]

### Financial / tax instruments

[CRA, PILOT, infrastructure commitment.]

### Water / hydrology hook

[Water draw, source, wastewater path.]

### Hydrology screen

[7Q10 ratio, effluent path.]

### Regulatory record (status as of {date})

[Air PTI, NPDES stormwater, SOS registrations — each tagged verified/open.]

## {N} — No other activity found

[RSEI check, ECHO check, web sweep result — all cited and tagged.]

## Instruments to pull (priority order)

1. [Primary resolution/deed/permit instruments, in order of evidentiary value]

## Sources

- [URL] — [description]
```

## What "no activity found" means

A clean sweep is a result, not a failure. If RSEI, ECHO, and web search turn up no data-center
project, write a "No activity found" section citing each negative check:

- RSEI county inventory: no NAICS 518210 entry
- ECHO NPDES: no data-center-type permits
- Web sweep: no council resolutions, no trade-press coverage

A negative result tagged `[verified]` is valid and protects the record.
