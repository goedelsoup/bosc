# BOSC water-balance run — assimilative screen + the new sanitary figures

**Run:** `watermark hydro` (live) + the committed `buildout` scenario, 2026-06-08.
**Engine:** Tier-0 water balance + 7Q10 low-flow assimilative screen
(`watermark.hydrology`). Tier-0 is an auditable screen, **not** a SWMM/HEC-RAS result.
**Live streamflow:** Ottawa River at Lima, NWIS gage `04187100` (today ~90.5 cfs /
58.5 MGD — *ambient* flow, well above the regulatory low-flow design condition).

This memo records the run and folds in two newly **document-sourced** figures from
the commissioners' minutes ([sanitary-economics.yaml](sanitary-economics.yaml)) that
the model did not previously carry.

## Headline

**All three County receiving streams already FAIL the 7Q10 low-flow dilution screen
at their design flows — before any data-center load.** The Ottawa River's regulatory
7Q10 is **0.20 cfs (≈0.13 MGD)**; the BOSC campus's *consumptive cooling draw alone*
is modeled at **3.14–10 MGD** — i.e. the data center's evaporative loss is **24–77×
the receiving river's 7Q10 low flow**.

## The assimilative screen (Tier-0, 7Q10 dilution)

| Discharger | Receiving water | 7Q10 (cfs) | Discharge (cfs) | Dilution | Flag |
|---|---|---:|---:|---:|---|
| Shawnee II WWTP | Ottawa River | 0.20 | 4.64 (3.0 MGD) | 0.04:1 | **violation** |
| American Bath WWTP | Pike Run | 0.03 | 2.32 (1.5 MGD) | 0.01:1 | **violation** |
| American II WWTP | Dug Run | 0.78 | 1.86 (1.2 MGD) | 0.42:1 | **violation** |

*Source: NPDES fact sheets (2IG00001 Ottawa/Lima Refining; 2PH00007 American Bath;
2PH00006 American II) [verified]. 3 checks, 3 violations — the receiving waters are
effluent-dominated at low flow.*

## The BOSC cooling load (buildout scenario, sourced)

- **IT load 275 MW** [document — OEPA Air PTI P0138965, committed `permits/4132514.epa.yaml` (final, 2026-05-28); 114 gensets × 2.75 ekW ≈ 313 MW backup (per-engine ekW from the draft public notice — CBI-redacted in the final permit); IT 250–300 MW N+1].
- **Makeup demand ≈ 3.92 MGD**; **consumptive 3.14 MGD** (power × WUE 1.8 L/kWh [assumption]) to **10 MGD** (FM-2 2.5 MGD blowdown × (CoC−1) [derived]). The two methods disagree ~3× — the consumptive draw is the model's dominant uncertainty.
- Drawn on **Lima's Ottawa/Auglaize supply** (7Q10 0.20 cfs). A 3–10 MGD consumptive loss on a river whose low-flow design condition is 0.13 MGD is the core assimilative concern.

## New from the minutes (folded in here)

1. **Interim BOSC sanitary discharge: 0.13 MGD at 83 °F** ([sanitary-economics.yaml](sanitary-economics.yaml); minutes 2025-07-29) [document]. Two notes:
   - **Thermal.** 83 °F is a warm return; the model carries flow but not temperature. A warm discharge into a low-flow stream is an additional (unmodeled) assimilative stressor — flagged for a thermal screen.
   - **Scale coincidence.** The *interim* sanitary flow (0.13 MGD) happens to equal the Ottawa 7Q10 (0.13 MGD) — i.e. even the small early-phase return matches the river's entire 7-day-10-year low flow.
   - The **permanent** return is the FM-2 **2.5 MGD** industrial discharge already in the model.
2. **The Cridersville / Shawnee Oaks reroute loads the worst-violating node.** The County is rerouting ~200+ homes + the Shawnee Oaks domestic flow onto **Shawnee II** (the $1M 0% loan, #137-26) — the same plant that already screens at **0.04:1** on the Ottawa. The reroute adds domestic flow on top of the BOSC industrial return to the most over-allocated receiving water. (Not yet quantified in MGD in the record — followup.)

## What the run shows

- The municipal loop's WWTPs are **already effluent-dominated** at low flow (2–25× over a 1:1 dilution); BOSC is added on top of a failing baseline, not a clean one.
- BOSC's **consumptive** cooling draw (3–10 MGD) is large relative to the Ottawa's low-flow supply — a withdrawal concern distinct from the discharge concern, and consistent with the residents' well-drawdown questions in the PAAC minutes.
- The County's own **reroute** concentrates more flow on Shawnee II → Ottawa, the worst-screening node.

## Caveats

Tier-0 screen only. The 7Q10 is the cited regulatory low-flow (NPDES fact sheets); the
live NWIS reading only sanity-checks ambient flow. WUE and cycles-of-concentration are
**assumptions** (low confidence); the 3–10 MGD consumptive range is the headline
uncertainty. The 83 °F thermal effect is noted, not modeled. Figures from the minutes
are OCR-approximate discussion items — verify against the source PDFs.

## Cross-references

- [sanitary-economics.yaml](sanitary-economics.yaml) — the 0.13 MGD @ 83 °F, the reroute, the fees
- [bosc-resolution-ledger.yaml](bosc-resolution-ledger.yaml) — #469-25/#713-25/#137-26 (PS+FM, CMAR)
- `data/scenarios/buildout.scenario.yaml` — the sourced cooling basis run
- `data/reference/hydrology/` — 7Q10 (`low-flow-7q10`), TMDL WLAs, sanitary basis
- [docs/HYDROLOGY.md](../../../docs/HYDROLOGY.md) — the full generated hydrology dossier
- `data/extracted/regulatory/wastewater-enforcement-history.yaml` — Shawnee II capacity history
