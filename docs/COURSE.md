# Project BOSC — Research Course

> **Status:** living draft. This charts *what we're investigating* and, in
> sequence, *what we built* to investigate it. Inquiry drives engineering.
>
> **Where the inquiry stands.** The deconstruction phase answered the two first
> questions: **what** it is (a hardened ~275 MW data-center campus on the N. Cole
> corridor) and **who** it is for (**Google** — now on three independent corpus
> sources: the **AEDG release**, the PAAC minutes, and the LACRPC minutes; see
> [DOSSIER §1](DOSSIER.md)). The course now turns from *identification* to
> *analysis and forecasting*: the **beneficiaries** and how they correlate to the
> broader data-center boom, the **compute capacity and workloads** the plans imply
> (the GovCloud question is substantially answered — Liz Schultz's "classification
> levels"), the **Maumee watershed comparison** (does Fort Wayne mirror the
> dilution thesis?), and **localized economics** beyond utility consumption. See
> §1.5 for the forward tracks.
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

The thesis, now **established** by the corpus: a Google data-center campus is
driving a coordinated build-out of public road and utility capacity on the Cole
Street corridor, with the port authority as the financing/land vehicle.
`[verified: DOSSIER §1, §6–§7]` The live questions have moved downstream — **who
benefits and at what public cost**, **what the campus consumes and runs**, and
**how this fits the national pattern** — the forward tracks in §1.5.

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

### 1.4 Corridor context — open leads `[open]`

Regional context for the cloud-consumer-economics axis. These are **questions and
leads, not platform facts** — none are asserted in the dossier or entered into the
entity graph until a document backs them. Defense-ecosystem actors appear only
where the public record already places them, as `[open]` context.

- **Mineral rights / oil-gas preemption.** Recorded mineral severances or pipeline
  easements in the corridor, and **ORC §1509.02** (ODNR preemption of local
  oil/gas regulation) — applicability `[open]`; needs the Recorder instruments.
- **Rail.** The **CSX Toledo Subdivision** ROW and any spur, with **49 U.S.C.
  §10501** federal preemption — existence of the ROW is documented; project use
  `[open]`.
- **Parallel consumers (other counties).** **Thor Equities / Thor Van Wert /
  Highland55** (Urbana, Van Wert); **CyrusOne**; **Platon Investments / Dynamo
  Ventures** (TX, shared-organizer overlap with Montfort) — corridor `[open]`; no
  in-corpus document yet (Platon/Dynamo rest on a third-party aggregator profile).
- **Roshel / International Motors (Springfield APA, 2026-03-30).** Logged strictly
  as **corridor context, not a connection** — the evidence does not link it to
  BOSC, and it must **not** enter the entity graph.

### 1.5 Forward tracks — from identification to forecasting

With *what* and *who* settled, five tracks carry the inquiry forward. Each is an
analysis, not a missing document.

1. **Beneficiaries & relation classes.** Move the entity graph past *mechanical*
   edges (who conveyed to whom) to the **nature** of each party's tie to the
   project: direct approval, direct management, direct beneficiary, possible
   end-user, environmental beneficiary, and relations to other government bodies.
   The graph stays corpus-verified — this is a classifying overlay, not new
   parties (Google stays an annotation, not a node). `[in progress]`
2. **Compute capacity & workloads.** Translate the disclosed plant — ~313 MW
   backup / ~275 MW IT, 36 cooling towers — into a *capacity* reading and the
   **workload classes** it fits. The **GovCloud** question is substantially
   answered: Liz Schultz addressed it in indirect language ("classification
   levels"). Associate the capacity with concrete workload profiles and price the
   GovCloud premium. `[analysis]`
3. **The Maumee watershed comparison.** Lima's discharges screen as effectively
   undiluted at low flow. Does **Fort Wayne** — and the other large Maumee Basin
   dischargers — mirror that dilution thesis, or is Lima distinct? A basin-scale
   read using the ECHO NPDES inventory already in the corpus. `[analysis]`
4. **Hydrology, expanded to hypotheses.** Reflect that BOSC output routes to
   **Lima (FM-2)** and **American II (FM-1)** only; **Shawnee II has no known
   routing** (the FM-3 lead is theorized, not confirmed). Then run hypotheses at
   three levels — **macro** (Maumee basin), **local** (Lima loop), **site**
   (per-campus / per-WWTP). `[in progress]`
5. **Localized economics.** Move past utility consumption to quantitative local
   baselines — **population over time, employment by industry, export
   orientation** — so the economic argument is grounded in the place, not only in
   qualitative entity research. `[in progress]`

These feed [the bigger picture](bigger-picture.md), [Economics](ECONOMICS.md),
and [Hydrology](HYDROLOGY.md).

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
   resolves onto the *same* Bistrozzi node as the deeds). **Sweep complete: all 30
   EPA Section-401 / DSW / USACE permit-action PDFs in `permits/` are extracted**
   (`data/extracted/permits/*.epa.yaml`) — 26 high-confidence, 4 medium (the
   medium are delineation reports / cover pages where the visible number is an
   internal project no., not an agency-issued permit — flagged, not errors).
   Findings: Bistrozzi LLC and Tilted Gate LLC share a Wilmington DE mailing
   address (2801 Centerville Rd, PMB); a second codename **"Project Dazzler"**
   (Tilted Gate, USACE 404, principal Timothy Chadwick); counsel Vorys
   (Tangeman/Ziance), engineer EMH&T.
3c. **Wetland-determination extractor (`kind=wetland`).** `[done]` — the 2
   USACE Wetland Determination Data Forms in `permits/` are a different shape than
   the permit-action letters (a field-botany point-sample worksheet), so they get
   their own kind. `bosc.models.WetlandDetermination` captures the sampling point,
   location/coords, applicant, and the three regulatory criteria (hydrophytic
   vegetation / hydric soil / wetland hydrology → is_wetland). Both points
   (`WD-1`, `WE-1`, `*.wetland.yaml`) tie to **Project BOSC** on the Bistrozzi
   parcels (Sugar Creek Twp/Allen, former soybean field, hydric Westland-Rensselaer
   soils): each is formally **not a wetland** despite hydric soil + wetland
   hydrology, because hydrophytic vegetation is absent due to farming disturbance.
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
   couples event runoff into the balance. The HSG is now **SSURGO-sourced** (`connectors.
   ssurgo`: the footprint's grid-sampled dominant hydrologic soil group via USDA Soil Data
   Access), falling back to the cited "C" assumption offline — SSURGO actually shows the
   footprint is predominantly dual **B/D** (tile-drainable lake-plain lows) with upland B,
   not C.
10. **Scenario diffing + dossier.** `[done]` — Increment 3. `bosc scenario` (+ agent
   `hydrology_scenario` tool) evaluates **baseline vs data-center buildout** on the
   cooling consumptive-fraction knob (`bosc.hydrology.scenario`): the campus draws
   cooling water from the same Ottawa/Auglaize supply the WWTPs discharge to, and the
   evaporated fraction is a net basin loss. Results persist to committed, self-auditing
   `data/scenarios/{baseline,buildout}.scenario.yaml`. The new grounding that makes it
   land: the **Ottawa mainstem 7Q10 is now cited at 0.2 cfs** (Lima Refining fact sheet
   2IG00001, USGS 04187100; 1Q10 = 0 cfs — the river nearly dries at design low flow,
   heavily abstracted upstream for Lima's own supply), which also un-skips Shawnee II →
   Ottawa in the assimilative screen (now a violation, 0.04:1). `bosc hydro-report`
   renders the whole Tier-0 story as the evidence-tagged [`HYDROLOGY.md`](HYDROLOGY.md)
   dossier (regenerable).
11. **Sourced cooling design basis.** `[done]` — replaces the bare "5 MGD, TBD"
   assumption with `bosc.hydrology.cooling.derive_cooling_basis`, a basis *derived* from
   disclosed campus data by two independent cited methods: top-down **power × WUE** (OEPA
   air permit P0138965: 114 gensets × 2.75 MW ≈ 313 MW backup → ~275 MW IT load × ~1.8
   L/kWh evaporative WUE → ~3.1 MGD consumptive) and bottom-up **blowdown × cycles** (the
   documented 2.5 MGD FM-2 discharge at ~5 cycles → ~10 MGD upper bound). They disagree
   ~3× (FM-2 isn't purely cooling blowdown), so the basis reports the **3.1–10 MGD**
   range; the buildout scenario defaults to the conservative power-based central
   (overridable via `--cooling-demand`). Headline is now sourced and robust: even the low
   estimate = **4.85 cfs net basin loss ≈ 24× the Ottawa 7Q10**; the upper bound ~77×.
   Inputs are document/assumption-tagged, demands `derived`.
12. **Tier-1 escalation — EPA SWMM.** `[done]` — `bosc tier1` (+ agent `tier1_swmm` tool)
   runs the real EPA SWMM5 engine (`bosc.hydrology.swmm`, via pyswmm) for two questions
   Tier-0 only approximated. **Detention sizing:** bisect a basin's bottom-orifice
   diameter until the released post-development peak matches the pre-development peak —
   for the 25-yr storm, SWMM finds **post 579 vs pre 215 cfs**, held by a **~42 ac-ft**
   basin. **Sanitary wet-weather surcharge:** dry-weather base + RDII gives a **~16.9 MGD**
   storm peak that **exceeds both** documented plant peak capacities (American II 3.6,
   Shawnee II 12.6 MGD) — i.e. SSO risk, tying to the 1996 consent decree. The engine is a
   native extension that may not load (it gets `Killed: 9` under macOS hardened runtime on
   some wheels — ad-hoc `codesign` the swmm-toolkit dylibs to clear it); everything
   **degrades gracefully** via a subprocess availability probe (tests skip, CLI reports
   unavailable). Footprint/storm/plant-capacities stay document/connector-sourced; the
   network + hydraulic params (imperviousness, RDII R-T-K, basin geometry) are flagged
   assumptions, since we lack the as-built drainage network.

13. **Ground the detention result in the real civil design.** `[done]` —
   `bosc storm-plan` (+ agent `storm_plan_inventory` tool, `bosc.hydrology.stormplan`)
   transcribes the campus **grading & stormwater plan** (sheet `1A-C-3104`, EMH&T 95% SPS,
   *Not For Construction* — the `.odg` under `plans/bistrozzi-plans/`) into a reviewed
   artifact (`data/extracted/plans/lma1a.storm-inventory.yaml`). The sheet's pipe
   connectivity/inverts are vector geometry with **no schedule table**, so a routable SWMM
   network is *deliberately not fabricated* (omission over invention). What it does state we
   ground: the storm-structure **rim population** (207 labels, 820.5-828.75 ft, ~8 ft relief,
   document-cited) and the conveyance inventory (catch basins, curb/inlet, storm sewer,
   headwall outfalls, rock check dams, overland flood routing). The headline grounded fact —
   **no detention, retention, or infiltration storage is shown** (the negative is auditable:
   seven storage terms searched, all absent) — reframes item 12's basin: it is the on-site
   control the as-drawn 95% design **omits**, not a modeled redesign. Wired into `bosc tier1`
   (the detention finding now cites the sheet) and the dossier's Tier-1 section.

14. **Ground the sanitary surcharge in cited design flows + the SSO mandate.** `[done]` —
   the surcharge had rested on a flat assumed base flow and an invented RDII rate.
   `bosc.hydrology.sanitary` loads a vendored cited table
   (`data/reference/hydrology/sanitary-basis.yaml`, the 7Q10-table pattern) of per-plant
   **permitted average / peak hydraulic** design flows — American II 1.2/3.6, Shawnee II
   3.0/12.6 MGD (peaking factors 3.0x, 4.2x) — from the OEPA NPDES permits + watch-items;
   American Bath's peak is **omitted** (uncited, not guessed). The surcharge now compares the
   campus's wet-weather contribution against each plant's **documented wet-weather headroom**
   (peak − average): 16.9 MGD vs American II's 2.4 and Shawnee II's 9.6 MGD. The campus dry
   base is the **document-cited 2.5 MGD FM-2** discharge (RDII R stays a flagged assumption).
   The decisive context is regulatory and now surfaces as a finding: the collection system is
   already under a **2005 OEPA mandate to eliminate all SSO bypassing by 2015**, with **$11.8M**
   of storm-water I/I remediation and a **21→48-inch trunk** rebuilt purely to equalize
   wet-weather I/I (1996 federal CWA consent decree; Allen County CNA-2005) — so the headroom
   is documented as effectively already spent. `bosc tier1` + agent `sanitary_basis` tool +
   the dossier's Tier-1 section. (Indian Brook pump-station as-built is scan-only — vision
   extraction deferred.)

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
