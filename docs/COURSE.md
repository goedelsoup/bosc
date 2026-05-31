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
   `[verified: data/extracted/roundabouts.summary.opc.yaml]`
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

### Phase A — unlock the highest-leverage genres
1. **Deeds extractor (`kind=deed`).** Grantor/grantee/parcel/consideration/
   instrument/date. Highest leverage: answers the land-ownership thread and is a
   well-structured target. Many recorder PDFs are scans → vision path.
2. **NPDES permit extractor (`kind=npdes`).** Facility, permit no, applicant,
   outfalls, effluent limits, receiving water, public-notice dates. These have
   clean text layers `[verified]`, so a text-first read is cheap and accurate.

### Phase B — entities and breadth
3. **Building-permit + SoS extractor (`kind=permit`).** Permit metadata; LLC
   officers/agents/registered addresses for entity resolution.
4. **Plan read (`kind=plan`).** Single-shot vision description of the site plan.

### Phase C — the cross-document layer (where the research lives)
5. **Entity/parcel resolution.** Link addresses, parcel IDs, and party names
   across deeds/permits/NPDES into a small entity graph.
6. **Timeline assembly.** Merge dated events from every extraction into one
   chronology.
7. **Corridor view.** Tie facilities/parcels/roadwork to corridor geography
   (we deliberately left Periplus's GIS behind; decide if/what to rebuild).

### Phase D — close the deferred carve-outs (as they block inquiry)
- Section-subtotal **accuracy** (self-correcting reconcile loop / Opus A‑B).
- **`extract-all`** sweep + assembled `OPCSummary` for the roadwork.
- Retire the legacy `OPCSummary` 25% hardcode; unify the hand-authored detail
  YAML onto the generic `Estimate` shape.
- New agent tools over the new structured data (query deeds, permits, timeline).

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
  County Engineer, a reconciliation memo, an entity/timeline dossier?
