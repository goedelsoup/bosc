# Project BOSC — Research Course

> **Status:** living draft (v0). This charts *what we're investigating* and, in
> sequence, *what we need to build* to investigate it. Inquiry drives engineering.
>
> **Evidence discipline:** claims below are tagged `[verified]` (read directly
> from a source document or committed extraction, with a citation),
> `[filename]` (suggested by a file/folder name, not yet read), or `[open]`
> (a question, not a finding). Never promote a `[filename]`/`[open]` to a fact
> without extracting and citing the source.

---

## 0. Where we are

A working three-stage platform (`ingest → extract → analyze`) with a
Claude-driven agent layer. Extraction is generalized within one document
kind — **OPC cost estimates** (contractor-agnostic `Estimate` + format
profiles) — and validated live against the Tetra Tech roundabout sheets.

The corpus is **wider than the extractor**: 56 raw documents across 7
collections (`aedg`, `oepa`, `recorder`, `permits`, `plans`, `regulatory`,
`sanitary`), of which only the 2 OPC sheets are extracted. The other ~54 are
deeds, NPDES permits, building permits, and plans — genres we cannot yet parse.

---

## 1. The line of inquiry

### 1.1 The landscape

Activity clusters on the **North Cole Street corridor in Allen County (Lima),
Ohio** — a single geography touched by four threads that are normally separate:

1. **Privately-funded public roadwork.** Six Tetra Tech OPC estimates
   (~$14.2M) for roundabouts and corridor work at Cole/Diller, Cole/Bluelick,
   the Primary Access Entrance (Beery Rd & N. Cole), Cole/West (SR 115), and the
   Cole & Bluelick corridors — privately funded via a BOSC Team deposit to the
   port authority (PAAC), dedicated to the County on completion.
   `[verified: data/extracted/aedg/roundabouts.summary.opc.yaml]`
2. **County utility capacity.** County-operated wastewater plants on the same
   roads — **American II WWTP** (3230 N. Cole St; NPDES 2PH00006; applicant
   Allen County Board of Commissioners; discharge nr. 4140 Diller Rd),
   **American Bath WWTP** (3226 N. Cole St; NPDES 2PH00007; receiving water Pike
   Run), and **Shawnee II WWTP** (NPDES 2PK00002; Ottawa→Auglaize→Maumee→Lake
   Erie). `[verified: data/documents/oepa/*-fact-sheet.pdf]`
3. **Land assembly.** A port-authority deed recorded 2025-11-18 referencing
   Amazon, plus parcel deeds tied to a developer entity. `[filename:
   data/documents/recorder/port-authority/202511180011830-amazon-deed.pdf,
   recorder/bistrozzi-deeds/]`
4. **Developer entities.** Building-permit sets and Secretary-of-State filings
   for codenamed entities (`bistrozzi`, `dazzler`) including LLCs such as
   Magenta Capital, Tilted Gate, and a "Bistrozzi Addition." `[filename:
   data/documents/permits/]`

The thesis to test: **a large private development is driving a coordinated
build-out of public road and utility capacity on the Cole Street corridor, with
the port authority as the financing/land vehicle.** Who pays, who benefits, who
owns the land, and whether the public cost is proportionate are the open
questions. `[open]`

### 1.2 Core research questions

- **Roadwork.** What is the full scope and cost, and does the OPC reconcile to
  the funding instrument? Who bears cost overruns? (We have the estimates; we
  lack the agreement/funding docs.)
- **Utilities.** What discharge capacity do the WWTP permits authorize, who is
  the served customer base, and is new capacity tied to the development?
- **Land.** Grantor→grantee chain for the port-authority/Amazon parcels and the
  developer deeds; consideration; dates; parcel IDs.
- **Entities.** Who controls the codenamed LLCs (officers, agents, addresses),
  and how do they relate to the port authority and to Amazon?
- **Environment/history.** What do the 1996 CWA consent decree and sanitary CNA
  establish about prior obligations on this system?
- **Timeline.** A single chronology linking permits, deeds, SoS filings, and the
  roadwork agreement.

### 1.3 What each collection can answer

| Collection | Genre | Supports | Extract targets |
|---|---|---|---|
| `aedg` | PRR bundle (OPC + ?) | roadwork scope/cost | OPC estimates (done); other pages `[open]` |
| `oepa` | NPDES permits/fact-sheets | utility capacity, discharge | facility, permit no, applicant, outfalls, limits, receiving water, dates |
| `recorder` | deeds | land ownership chain | grantor, grantee, parcel id, consideration, instrument no, date |
| `permits` | building permits + SoS | development scope, entity control | permit no, parcel, valuation, applicant; LLC officers/agents |
| `plans` | site plan (`.odg`) | site layout | vision read of the plan |
| `regulatory` | consent decree, CNA | prior obligations | parties, obligations, dates |
| `sanitary` | as-built | utility infrastructure | facility, location, date |

---

## 2. The engineering, sequenced to the inquiry

The dispatch seam already exists (`extract_page(kind=…)`); today only `opc` is
registered. Each new genre is **a new `kind` + structured model + profile**,
reusing the OPC pattern (hybrid OCR+vision read → forced-tool-use → Pydantic
validation → provenance). Order is driven by inquiry leverage.

### Phase A — unlock the highest-leverage genres ✅ done
1. **Deeds extractor (`kind=deed`).** Grantor/grantee/parcel/consideration/
   instrument/date. `[done]` — validated live and swept across `recorder/`;
   reproduces Periplus's hand-curated parcel ledger 11/11
   (`tests/test_periplus_crosscheck.py`).
2. **NPDES permit extractor (`kind=npdes`).** Facility, permit no, applicant,
   outfalls, effluent limits, receiving water, public-notice dates. `[done]` —
   text-first read, swept across all 9 `oepa/` docs.

### Phase B — entities and breadth
3a. **SoS business-filing extractor (`kind=sos`).** `[done]` — vision-primary
   read of Secretary-of-State LLC filings (`bosc.models.BusinessFiling`): entity
   name, filing id, formation jurisdiction, registered agent + address, organizer.
   Swept the three `permits/bistrozzi-permits/sos-*` filings (all Delaware foreign
   LLCs); feeds the entity graph with `organized_by` / `registered_agent` edges and
   a `shared_agent` shell signal. Surfaced: Magenta Capital + Tilted Gate share a
   registered agent (Corporation Service Company) **and** organizer (Michael
   Montfort); Bistrozzi Addition uses CT Corporation / Scott Ziance.
3b. **EPA permit-action extractor (`kind=epa`).** `[done]` — *the `permits/`
   collection is not building permits.* It is a stream of **Ohio EPA Division of
   Surface Water** actions on the project: Permits-to-Install (sanitary sewer),
   401 Water Quality Certifications / Isolated Wetland Permits, USACE Section 404,
   plus dated agency correspondence (incomplete notices, comment letters).
   `bosc.models.EpaPermitAction` captures the letter header (agency, program,
   permit no, action, dates, applicant + address, contact + firm, project,
   affected resource). Text-first read; feeds the timeline (regulatory milestones)
   and entity graph (`represented_by` / `affiliated_with`; the EPA applicant
   resolves onto the *same* Bistrozzi node as the deeds). Validated live on 5
   representative docs — **remaining ~25 not yet swept.** Findings: Bistrozzi LLC
   and Tilted Gate LLC share a Wilmington DE mailing address (2801 Centerville Rd,
   PMB); a second codename **"Project Dazzler"** (Tilted Gate, USACE 404, principal
   Timothy Chadwick); counsel Vorys (Tangeman/Ziance), engineer EMH&T.
   *(The 2 Army-Corps wetland-delineation data forms are a different shape — a
   later `kind`.)*
4. **Plan read (`kind=plan`).** `[done]` — an `.odg` is a *vector* drawing, so
   `bosc.documents.read_odg` extracts the titleblock/legend/callout TEXT (the
   authoritative content) plus the preview thumbnail, tolerating the file's bad
   CRC via a raw zlib inflate. `SitePlan` captures project, sheet, discipline,
   phase, scale, the design team, and legend `key_features`. Validated live on
   `LMA1A-95-SPS`: **"American Industrial Park Site," Lima** — Grading & Storm
   Plan, 95% SPS, by EMH&T (Civil) / CI Design (Architecture, Boston) / WSP USA
   Buildings (MEP, Troy NY); features include a **substation, anti-ram barriers,
   security fence, containment areas, fiber duct bank** — the signature of a
   hardened data-center campus.

### Phase C — the cross-document layer (where the research lives)
5. **Entity/parcel resolution.** `[done]` — `bosc.pipeline.entities`: normalize
   party names to a canonical key, merge variants, classify conservatively
   (government / corporate / individual / trust / facility / water; flag Delaware
   as a *signal*, not a verdict), and link conveyances / utility operation /
   discharge. `bosc entities` + agent `entities` tool. Resolves Bistrozzi's four
   acquisitions and the Port-Authority→Amazon edge. Facilities key on their base
   permit number; deeds-side person/trust resolution is still coarse (long
   trustee recitals form their own nodes — refine when SoS data lands).
6. **Timeline assembly.** `[done]` — `bosc.pipeline.timeline`: one sorted
   chronology across deeds/NPDES/OPC, deduped across corroborating artifacts.
   `bosc timeline` + agent `timeline` tool.
7. **Corridor view.** `[open]` Tie facilities/parcels/roadwork to corridor
   geography (we deliberately left Periplus's GIS behind; decide if/what to
   rebuild). Frozen corridor/parcel geojson is in `data/reference/periplus/`.

Both built on `bosc.pipeline.corpus` — a loader that reads every committed
extraction into one typed `Corpus`, classified by content shape.

### Phase D — close the deferred carve-outs (as they block inquiry)
- **Entity-graph polish** `[done]` — contact-resolution noise cleaned
  (multi-value `;` split; middle-initial merge; no self-affiliation).
- **Unify the hand-authored detail YAML** `[done]` — `bosc.pipeline.corpus`
  parses the bespoke `roundabouts.detail.opc.yaml` into the generic `Estimate`
  shape *in memory* at load (markers preserved on disk per data discipline), so
  it joins `corpus.estimates` and reconciles (7/10 — the 3 fails are the known
  pre-existing ROADWAY/PAVEMENT transcription gaps). No more `corpus.unrecognized`.
- **Agent tools over the structured data** `[partly done]` — `timeline` and
  `entities` tools added; `program_overview` / `reconcile_estimate` already exist.
- Section-subtotal **accuracy** `[open]` (self-correcting reconcile loop / Opus A‑B)
  — needs live re-extraction; the 3 detail discrepancies are the test case.
- **`extract-all`** sweep + assembled `OPCSummary` for the roadwork `[open]`
  (live OPC sweep of pages 318-327); retire the legacy 25% hardcode then.

### Phase E — hydrological forecasting (water / stormwater / sewage)
The platform's first move from *deconstruction* to *forecasting*. The Lima system is
one closed flow loop on two rivers — **Auglaize/Ottawa → Lima WTP → municipal +
data-center demand → county/Lima WWTPs → Ottawa River** — and the binding constraint
is the Ottawa's (and its tributaries') **low flow**. We bring over Periplus's *Tier-0
design idea* (SCS-CN + mass-balance) as document-grounded Python, not its solver/GIS
stack. Every numeric input is a `ProvenancedValue` tagged `document|connector|
assumption|derived`. (`bosc.hydrology`, see [the plan](../../.claude/plans/splendid-roaming-peacock.md).)

8. **Water-balance spine + low-flow assimilative screen.** `[done]` — Increment 1.
   `bosc hydro` (+ agent `hydrology_balance` tool) assembles the WWTP discharges (cited
   design flows from `watch-items.geojson`) routed to their receiving waters, grounds the
   abstraction reach with **live USGS NWIS** streamflow (Ottawa at Lima, gauge 04187100;
   offline-aware cache + committed fixtures), and screens each discharge against the
   stream's **cited 7Q10** (`data/reference/hydrology/low-flow-7q10.yaml`, read from the
   Ohio EPA fact sheets in our corpus). Headline finding, document-grounded: the two
   county plants on tiny tributaries discharge **more than the stream's entire 7Q10** —
   **American Bath → Pike Run 0.01:1**, **American II → Dug Run 0.42:1** dilution (both
   `violation`; the American II fact sheet states the acute ratio itself as 1.3:1).
   Shawnee II → Ottawa mainstem has no cited 7Q10 and is **skipped, not invented**.
9. **SCS-CN stormwater runoff.** `[done]` — Increment 2. `bosc storm` (+ agent
   `stormwater_runoff` tool) runs the Tier-0 SCS chain (`bosc.hydrology.solver`:
   Type-II rainfall → curve-number excess → SCS unit-hydrograph convolution; plus a
   Muskingum-Cunge routing module) for a **pre- vs post-development** design storm over
   the campus footprint. Rainfall is **live NOAA Atlas-14** (point query, offline cache +
   cited fallback); the footprint is document-sourced (recorded Bistrozzi parcels, ~340
   ac); land cover (prior use "Neff Farms" → cropland; campus → impervious) and HSG (Allen
   County → C) are cited assumptions; curve numbers from the cited TR-55 table
   (`cn-lookup.yaml`). Finding: paving the footprint lifts the **25-yr 24-hr peak ~373 →
   482 cfs (+109)** and runoff volume **~75 → 100 ac-ft** (+25 ac-ft of detention to hold
   post-development discharge to the pre-development rate).
   *Scope note:* this is the steady-state low-flow check's complement, not a coupling — a
   design storm is a different flow regime than 7Q10, so the storm does **not** "collapse
   the 7Q10 dilution"; the `stormwater` node seam stays inert until a wet-weather scenario
   couples event runoff into the balance. Live **SSURGO** HSG deferred (endpoint 404 at
   build; HSG is the cited assumption above).
10. **Scenario diffing.** `[open]` — Increment 3. Baseline vs data-center-buildout (the
   one-knob cooling consumptive-fraction lever, currently a cited 0-cfs assumption) →
   committed `data/scenarios/*.yaml`; dossier integration.

---

## 3. Immediate next steps (proposed)

1. Confirm/adjust this course.
2. Build the **deeds** extractor and run it on the port-authority/Amazon deed —
   first real test of a non-OPC `kind`, and it directly advances the land thread.
3. In parallel, the **NPDES** extractor over `oepa/` (cheap, text-first) to pin
   utility capacity and dates.
4. Stand up a minimal **timeline** from whatever the first extractions yield.

## 4. Decisions for you `[open]`

- **Scope/priority:** is the land-ownership thread the priority, or utilities,
  or roadwork-funding? That reorders Phase A/B.
- **GIS:** do we rebuild any corridor/parcel geography in BOSC, or stay
  document-only for now?
- **Output:** what's the deliverable of the research itself — a briefing for the
  County Engineer, a reconciliation memo, an entity/timeline dossier? *(First cut
  landed: [`DOSSIER.md`](DOSSIER.md) — an evidence-disciplined synthesis of the
  graph + timeline, regenerable as the corpus grows.)*
