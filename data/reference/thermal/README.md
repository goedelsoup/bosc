# `data/reference/thermal/` — thermal-discharge permitting methodology (EPA)

Federal methodology and regulatory-framework reference for **thermal discharges** under
the Clean Water Act NPDES program. This is the authoritative outside source that grounds
a *receiving-water thermal screen* — the heat-side peer of the chemical toxic screen that
[`data/reference/wqs/`](../wqs/README.md) grounds. All claims sourced from it are tagged
`[reference]`, never `[verified]` (it is published federal guidance, a prior the analysis is
held against — not a fact about any Lima receiving water).

## Contents

| File | What | Source |
|---|---|---|
| `epa-833-f-23-007-thermal-discharges-npdes-2023.pdf` | *Thermal Discharges in NPDES Permits: Overview of Resources and Tools*, 272 pp. (LFS). | EPA Office of Water, Water Permits Division, **EPA-833-F-23-007**, June 2023. |
| `great-lakes-ris-thermal-tolerances.yaml` | The **Great Lakes RIS thermal tolerances** derived from Table 3-5 of the guidance PDF (with Table 3-4 trophic/status context and the Table 3-6 references) — acute/chronic upper–lower + optimal thermal range, per species and life stage, °C. The biological limits for a §316(a) balanced-indigenous-community read. Read by `watermark.hydrology.thermal_criteria` (epic #1715, Phase 1). Values verbatim (ranges preserved). | Transcribed from **EPA-833-F-23-007** §3.3 Tables 3-4/3-5/3-6. `source: reference`. |

Provenance: retrieved 2026-07-21; `sha256 914f2576686459704ce56c416e57f6ebe1f1770fc24f4660fcdc4508da790c88`.
LFS-tracked via the `data/reference/**/*.pdf` rule in `.gitattributes`. Immutable — never
edit the source bytes; re-download to refresh and record a new checksum.

## What the document covers

- **§2 — NPDES thermal permitting framework.** Technology-based (TBEL) vs. water-quality-based
  (WQBEL) effluent limits for temperature; **thermal mixing zones**; the **CWA §316(a)** thermal
  variance (alternative thermal effluent limits / **ATEL** where standard limits are "more
  stringent than necessary to protect a balanced, indigenous community" — BIC); and how §316(b)
  cooling-water-intake rules interact (reducing intake flow raises effluent temperature — a
  §316(a)/§316(b) trade-off). Regulatory anchors: **40 CFR Part 125 Subpart H (§125.70–73)**,
  §124.8 fact sheet, §124.57 public notice.
- **§3 — Biological effects.** Thermal tolerances of **Representative Important Species (RIS)** by
  region — **Great Lakes** (the region for Lima → Maumee → Lake Erie), Pacific NW, Middle Atlantic,
  Inland Great Rivers — plus thermal-refugia heterogeneity. Tables 3-4/3-5 give the Great Lakes RIS
  and their acute/chronic/optimal temperature limits (e.g. walleye adult acute ≈ 34.4 °C, lake trout
  adult optimal ≈ 12–13 °C, northern pike, smallmouth/white bass).
- **§4 — Technical resources.** Review of hydrodynamic **thermal-mixing models** (CORMIX, Delft3D,
  EFDC, MIKE 3 FM, CE-QUAL-W2 — Tables 4-1/4-2); thermal monitoring equipment and TIR remote
  sensing; **thermal-mitigation** methods (cooling towers, hybrid/adiabatic systems, riparian shade).
- **§5 — Case studies.** Six well-formed §316(a) demonstrations (BP Whiting Refinery, Brayton Point,
  Quad Cities Nuclear, SJEC, VAPP, VYPNS) and EPA's Recommended Best Practices for thermal study
  design.

## Why it's here (the gap it fills)

The platform models the **water quantity** side of cooling (withdrawal / consumption / discharge
volume — `watermark.hydrology.cooling_models`) and the **chemical** side of discharge
(`watermark.hydrology.toxics` × `criteria`). It does **not** yet model the **thermal** side: the
heat load a cooling discharge carries, the temperature rise it drives in the receiving reach at a
design low flow, or how that compares to Ohio's temperature WQS and the §316(a) framework. The
once-through cooling model already computes a condenser ΔT internally (`_OT_DELTA_T_C`) — but only
to back out a *water volume*, never the in-stream thermal impact. This document is the methodology
that closes that gap.

## Scope & gaps

- **Federal guidance, not Ohio criteria.** The numeric temperature standards for a Lima screen are
  Ohio's, transcribed alongside the chemical criteria in
  [`data/reference/wqs/ohio-temperature-criteria.yaml`](../wqs/README.md) — not in this PDF. (They
  were *formerly* codified in **OAC 3745-1-07**; the chapter was reorganized and they now live in
  **OAC 3745-1-35** Table 35-11 (inland, by geographic zone), **3745-1-31** Table 31-1 (Lake Erie),
  and **3745-1-06** (O) Table 1 (thermal mixing zones).) This document supplies the *method*; Ohio
  WQS supply the *thresholds*; the Great Lakes RIS tables here supply the *biological* limits for a
  §316(a)-style read.
- **Screening, not a permit determination.** Any downstream thermal screen built from this is a
  fully-mixed, design-low-flow order-of-magnitude estimate — it flags where a §316(a)/mixing-zone
  analysis is *warranted*, it is not a CORMIX plume model or a permit decision.
- Disclaimer (§ front matter): the document "does not have the force and effect of law." Cite it as
  guidance/method, not as a binding requirement.

## Integration roadmap

Tracked under epic **#1715** (Phase 1 #1716 · Phase 2 #1717 · Phase 3 #1718 · Phase 4 #1719).

- **Phase 1 (#1716) — landed.** Ohio temperature criteria
  ([`../wqs/ohio-temperature-criteria.yaml`](../wqs/README.md)) + the Great Lakes RIS tolerances
  (`great-lakes-ris-thermal-tolerances.yaml`, above), both read by the
  `watermark.hydrology.thermal_criteria` loader (the heat-side peer of `hydrology.criteria`).
- **Phase 2 (#1717)** — a `watermark.hydrology.thermal` screen (heat load → receiving-water ΔT at
  design low flow → criterion / §316(a) framing), the heat-side sibling of `toxics.py`.
- **Phase 3 (#1718)** — facility wiring + ECHO-DMR (parameter 00010) validation.
- **Phase 4 (#1719)** — surface on the water/dilution feed + frontend.

<!-- catalog:begin (generated by `watermark catalog render`; do not edit inside) -->

**Cataloged datasets** — generated from `data/catalog/reference/`; run `watermark catalog render --apply` after editing an entry.

### `thermal` — EPA Thermal-Discharge NPDES Permitting Guidance (EPA-833-F-23-007)

Source: EPA Office of Water, Water Permits Division, Office of Wastewater Management · License: Public domain (U.S. federal government work) · Access: public · Site scope: basin-shared · Refresh: on-demand, last 2026-07-21

| file | type | lfs |
| --- | --- | --- |
| `reference/thermal/epa-833-f-23-007-thermal-discharges-npdes-2023.pdf` | application/pdf | yes |

### `thermal-ris-tolerances` — Great Lakes RIS thermal tolerances (EPA-833-F-23-007 Table 3-5)

Source: EPA-833-F-23-007 "Thermal Discharges in NPDES Permits" (June 2023), Tables 3-4/3-5/3-6 — verbatim transcription of the Great Lakes Representative Important Species thermal tolerances · License: Public domain (U.S. federal government work) · Access: public · Site scope: basin-shared · Refresh: on-demand

| file | type | lfs |
| --- | --- | --- |
| `reference/thermal/great-lakes-ris-thermal-tolerances.yaml` | application/x-yaml | no |

<!-- catalog:end -->
