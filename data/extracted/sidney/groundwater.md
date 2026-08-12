# Sidney — groundwater: the well census, and the aquifer-scope question answered

Issue [#1997](https://github.com/watermark-directory/the-watermark-directory/issues/1997), epic
#1275. Resolves lead **`AQUIFER-SCOPE`** (#1381), which existed because #1379 **refuted** the
original "sole-source-aquifer campus" framing and nothing had yet answered the two separable
questions that framing had confused: **where the wells are**, and **whether a designation covers
them**.

Every external claim below was retrieved by one agent and then **re-retrieved and recomputed by a
second whose job was to refute it**. Claims that did not survive that pass are recorded in
[What did not survive](#what-did-not-survive) rather than dropped, because two of them are traps a
future check would otherwise walk back into.

## The headline, in the order the question has to be asked

1. **A federally designated sole-source aquifer does cover part of Shelby County.** `[verified]`
2. **One of the City's two well fields is inside it; the other is not.** `[verified]`
3. **The campus is not.** It is **1.68 miles outside**, with zero overlap. `[verified]`

Point 3 is not a rehabilitation of the refuted premise — it is a **second, independent refutation
of it**, arriving from a federal boundary dataset rather than from soils. #1379 killed the claim
with SSURGO; this kills it again with geometry.

## 1 · The designation

The **Buried Valley Aquifer System (BVAS)**, designated under SDWA §1424(e) — **53 Fed. Reg.
15876** (May 4, 1988), FRL-3369-5, FR Doc. 88-9103, signed 1988-04-14 by U.S. EPA Region V
Administrator Valdas V. Adamkus on the petition of the Miami Valley Regional Planning Commission.
`[verified]` — read off the **original Federal Register page images** (govinfo package
FR-1988-05-04), not off an OCR layer, and re-downloaded byte-identically by the verifier.

⚠️ **Shelby County is both named and partly excluded by the same notice.** Finding 1 lists Shelby
among the nine counties BVAS serves; §III then says:

> "Also excluded is a portion of Class II aquifer in **Logan and Shelby Counties** in which ground
> water flows north and west…"

So **the county list cannot answer this question — only geometry can.** The notice carries no map
("Maps of the boundaries are available from the U.S. EPA Region V Office of Ground Water"). That
is exactly the shape of trap that produced the original claim.

**Geometry:** 75.210 km² — **7.07% of Shelby County** — is inside the designated area, across six
of the county's fourteen townships (Washington 32.4%, Loramie 27.8%, Orange 19.2%, McLean 12.2%,
Cynthian 7.4%, Turtle Creek 0.9%). **Clinton Township, which contains the campus, is 0.00%.**
`[verified]` — U.S. EPA national Sole Source Aquifer layer intersected with Census TIGERweb
subdivisions; recomputed by the verifier in EPSG:5070 equal-area with an independently written
shapefile reader.

⚠️ **The designated polygon merges TWO federal designations.** Ohio EPA's metadata lists both
**53 FR 15876** (the northern MVRPC petition) and **53 FR 25670** (the "OKI extension", 07/08/88)
against one "Greater Miami SSA" feature, and nowhere states which citation governs which part of
it. The northern petition is the one that plausibly reaches Shelby, but **which notice governs the
Washington Township well field is `[open]`** — cite the polygon, not a single FR number, until the
Region V boundary maps are obtained.

## 2 · The City's two well fields

The City of Sidney runs a blended system — per its own Consumer Confidence Reports and EPA SDWIS
(PWSID **OH7501214**), **seven active groundwater wells and three surface intakes**. `[verified]`

| field | what it is | inside the SSA? |
|---|---|---|
| **Great Miami River bedrock field** | 4–5 carbonate wells beside the water plant (S-1/2/3/5/6; S-4 abandoned). Ohio EPA setting "Carbonate Bedrock"; ODNR maps Lockport Dolomite / sub-Lockport, >100 gpm. | **0.00%** — ~5.1–5.8 km outside |
| **Washington Township field** | 3 sand-and-gravel production wells, the ~$22M / 10 MGD / 9-mile-transmission-main "Water Source Project" completed ~2017. ODNR names the source the *Loramie Ck Alluvial Aquifer* (SGf, >100 ft thick, 100–500 gpm); Ohio EPA's SWAP attribute calls the setting "Buried Valley". | **97.17%** of the City's 427-acre groundwater source area; 46 of 47 test/observation wells inside |

**This is a finding about the wells, and only about one of the two.**

Hydraulics from the census's own columns `[verified]`: the three Washington Township production
wells are 79 / 122 / 132 ft deep, cased 59 / 97 / 103 ft, static water level **8.6 / 8.9 / 8.6 ft**
below surface, reported test rates 1,500 / 1,102 / 1,999 gpm — corroborated by the City's 2024 CCR
("a shallow depth to ground water ratio"). The bedrock field's own wells are **not in the ODNR
census at all** (zero logged wells inside its inner management zone), so no depth or static level
can be given for it from this source.

⚠️ **None of the census's 13 MUNICIPAL-coded wells is Sidney's** — they belong to Jackson Center,
Fort Loramie and other village systems. Sidney's municipal wells are identified through Ohio EPA's
protection-area geometry and the City's own GIS, not through the `MUNICIPAL` use code.

## 3 · The campus

- **Zero overlap** with the designated SSA; nearest boundary **2,702 m (1.68 mi)** SSE, at
  40.245933, -84.170733. `[verified]`, reproduced independently to the metre in UTM 16N.
- ODNR maps the campus into the **Union City End Moraine Aquifer** — lithology Fsg, 25–100 ft,
  yield **5–25 gpm** — and into **no sand-and-gravel aquifer polygon at all**. `[verified]`
  Independent corroboration of #1379 from a different agency dataset than SSURGO.
- The parcel intersects **no groundwater source-water protection area of any public water system**
  — all 55 vertices tested against all 18 delineated groundwater SWPAs within ~10 km. `[verified]`
- Ohio EPA's own capture zones exclude it: the 5-year time-of-travel area for the bedrock field
  stops **3.37 km** short of the parcel, and the Washington Township one **4.45 km** short.
  `[verified]`
- ⚠️ **NEW: the campus is inside the City of PIQUA's surface-water source protection area**
  (PWSID OH5501211, delineated 2003-06-27) — the drainage upstream of Piqua's Great Miami intake.
  `[verified]` It is in none of *Sidney's* surface-water zones: Sidney's own intakes are upstream
  of where this site drains.

**`[open]` — the gradient.** No documented hydraulic gradient or potentiometric surface between the
campus and either well field was found, and **none is asserted here**. "Upgradient" remains
unstated. The defensible substitute is the agency's own capture-zone delineation, above.

**The honest relationship, stated once:** the campus is ~1.7 mi outside the designated area and in
no wellhead protection zone; but its 1.0 MGD municipal reservation is served by a **blended**
system, and part of that blend comes from the field that is 97% inside the designated aquifer. Both
halves are true and neither cancels the other.

## 4 · The `dewatering` half is not reachable, and that is the finding

The `groundwater` chapter accepts `drawdown` **or** `dewatering`. Only the first is available:

- **No dewatering record has been produced for this project.** No construction-dewatering permit,
  discharge authorization or wellfield appears in the corpus, and the profile commits no
  `dewatering_wellfield_relpath`. Lima's equivalent exists because Lima has a committed dewatering
  wellfield; Sidney has none to commit.
- So the chapter carries the **survey alone**, and this is recorded as a dated per-route negative
  rather than left to be inferred from an absent feed. Grading has been under way since
  2025-12-05, so a dewatering record could exist and simply not be public — that is an `[open]`,
  not a "no".

## 5 · The drawdown screen, and a number it was about to publish wrong

`data/reference/ohio-waterwells/shelby.csv` — **3,776 logged wells** (2,036 domestic, 23
public/semi-public, 13 municipal), Ohio DNR under R.C. 1521.05. The screen reduces it to the
Shelby **LIMESTONE** aquifer and runs a Theis cone for a hypothetical groundwater stress.

⚠️ **The stress was the wrong number until this issue.** `site_cooling_makeup_scenario` read the
cooling basis's `makeup_demand`, which for an undisclosed cooling method holds the evaporative
**upper-bound envelope** — tagged `assumption`, labelled *"NOT an estimate"*, and deliberately
withheld from `headline_makeup()` so no caller can publish it. Sidney would have screened
**3.59 MGD** (116 ft of apex drawdown) against a campus whose **contracted** makeup is
**0.0126 MGD** — 285× smaller, on the record since #1995, and drawn from municipal surface water.
Fixed to prefer the stated quantity, the same rule #1995 applied to the buildout scenario.

As screened: apex drawdown **8.3 ft** central against a **116 ft** saturated thickness (bracket
0.1–116 ft), **318** domestic census wells within the `[inference]` 23,908 ft radius of influence.
**`dewaters` is false here**, and that too was wrong until this issue: the flag was keyed on the
bracket's *deepest* plausible cone (highest Q, lowest transmissivity), which fires for almost any
rate in a low-transmissivity aquifer — so a 0.0126 MGD contracted makeup was publishing a
categorical "the aquifer cannot sustain this" off a central cone of 8 ft. It now carries the
central case, which is what the field always declared itself to be. The low-transmissivity end
still reaches the thickness and is retained as a **bounded caveat**: it bounds the concern, it does
not settle it. (Lima's dewatering finding is untouched — its central cone reaches its own 47 ft
thickness on its own, which is the check on the change.)

## What did not survive

Recorded because two of these are traps, not because they are interesting.

1. **"Two independent agency layers agree 60/60" — REFUTED, and it was the one real methodological
   failure.** Ohio EPA's SSA layer and U.S. EPA's national shapefile are **the same geometry**:
   identical vertex and part counts on all four Ohio polygons (Greater Miami 60,217 vertices / 19
   parts in both), symmetric difference 0.0015% of union. Ohio EPA digitized the petitioner maps;
   the national layer's only lineage is an export step. **The agreement is a tautology — never cite
   the two as mutual corroboration.** (Also: 55 of the 60 sampled points were trivially
   outside/outside.)
2. **"Ohio EPA's hydro/Aquifers MapServer silently returns 0 features for `inSR=4326`" — REFUTED.**
   Re-run side by side with `inSR=102100` at all three points, every pair returned byte-identical
   attributes. **Do not record this as a route hazard**; it would send the next check chasing a
   bug that does not exist.
3. The 2006 EPA Region 5 **transcription** in the corpus (`data/documents/wpafb/ssa/`, ingested for
   WPAFB under #1397) drops "**the petitioned portion of**" from the original SUMMARY, widening the
   designation's stated scope — plus three further divergences in the same paragraph. A finding
   about **another site's** artifact, recorded here and not fixed here.
4. Reported "centroids" were vertex means, not area centroids (up to ~300 m off). Immaterial —
   every load-bearing distance is edge-to-edge polygon geometry — but do not reuse them as
   centroids.
5. Two negatives were under-reported: the SWPA envelope returns **18** features, not 15 (the
   conclusion strengthens — still zero overlap), and one cited bedrock-area well (180482) is
   outside the 1.2 km set it was drawn from.
6. An EPA SDWIS "all fields null" negative was a **case-sensitivity error** — the endpoint returns
   fully populated rows under lowercase keys, which is where the seven-wells/three-intakes
   inventory above comes from.
