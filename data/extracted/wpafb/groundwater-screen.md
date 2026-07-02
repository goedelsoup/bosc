# WPAFB Groundwater Screen — Buried Valley Sole-Source Aquifer + TCE/PFAS Plume Overlay

The **defining WPAFB receiving-water dimension** (#463). WPAFB's water risk is **not** surface-7Q10
dilution — it is **groundwater**. This document defines the **buried-valley + plume overlay** as a
new analysis dimension the surface Tier-0 tools do not cover, and pins the two load-bearing claims
to the **primary sources that must verify them**. Status **as of 2026-07-02**.

**Discipline:** every headline claim below (the sole-source aquifer, and the TCE and PFAS plumes as
two distinct records) is currently carried in the `SiteProfile` as `[inference]`/`[reference]` with
**no primary cited source in the corpus**. Until each is verified against the primary record named
here, they stay **to-verify, not findings.** `[open]`

## Why a groundwater screen (not the surface screen)

The bound Tier-0 surface tools screen an outfall's design flow against the receiving stream's
7Q10. For WPAFB that screen is both **blocked** (no derived Great Miami / Mad River at-Dayton 7Q10
yet — the at-base reaches 03270000 / 03270500 were added to the basin table under #464 and populate
on the next `derive-low-flows` run) **and the wrong denominator**: WPAFB and the City of Dayton run
**production well fields** on a buried-valley aquifer, so the load-bearing quantity is **groundwater
supply**, not in-stream low flow. `[verified]` that this is a different screen; `[open]` on the
aquifer/plume specifics below.

## Claim 1 — Great Miami / Mad River Buried Valley Aquifer is a US-EPA sole-source aquifer

**Profile assertion (`hsg_citation`, `[reference]`):** "Dayton / WPAFB sits on the Great Miami /
Mad River Buried Valley Aquifer — glacial outwash sand & gravel, a US-EPA designated sole-source
aquifer (the Dayton municipal + WPAFB production well fields draw on it)."

**Status: to-verify `[open]`.** Verify against the **primary designation record**:

- **US-EPA Sole Source Aquifer (SSA) designation** under Safe Drinking Water Act §1424(e) — pull
  the Federal Register notice / EPA Region 5 SSA record for the **Buried Valley Aquifer System**
  (the Great Miami / Mad River glacial-outwash valley-fill). Confirm: designation date, the
  designated area boundary, and that it names the Dayton/WPAFB well-field reach. *Instrument:* EPA
  Region 5 Sole Source Aquifer program page + the FR notice.
- **USGS / ODNR buried-valley hydrogeology** — confirm the "glacial outwash sand & gravel,
  well-drained HSG A/B valley fill" characterization and the well-field dependence. *Instrument:*
  USGS Great Miami Buried Valley Aquifer reports; ODNR groundwater resources maps.
- **Miami Conservancy District (MCD)** — the MCD monitors the Great Miami Buried Valley Aquifer and
  publishes water-quality / water-level data; a secondary but authoritative corroborating source.
  `[reference]`

The profile header comment carries the two plumes as one phrase (`[inference]`): WPAFB "is the
source of a documented TCE / PFAS groundwater plume on that same drinking-water aquifer." **Do not
conflate them** — TCE (chlorinated solvent, legacy industrial/degreasing) and PFAS (AFFF
firefighting foam) are distinct plumes with distinct sources, regulatory tracks, and records. They
are split into two independently-sourced claims below; **verify and tag each separately.**

## Claim 2 — a documented TCE (chlorinated-solvent) groundwater plume on that aquifer

**Profile assertion:** the TCE component of the header-comment plume phrase (above), `[inference]`.

**Status: to-verify `[open]`.** Verify against the **primary environmental record**:

- **Air Force Installation Restoration Program (IRP) / CERCLA administrative record** — WPAFB is a
  long-standing IRP site; pull the CERCLA/RCRA administrative record for the TCE (trichloroethylene)
  groundwater plume(s), Operable Units, and any Record(s) of Decision. *Instrument:* AFCEC /
  WPAFB Environmental Restoration administrative record; EPA CERCLIS/SEMS.
- **ATSDR** — any TCE health consultation / public-health assessment for WPAFB groundwater.
  *Instrument:* ATSDR site records for Wright-Patterson AFB.
- **Ohio EPA (OEPA)** — DERR / drinking-water records for the affected well fields; source-water
  protection area delineations. *Instrument:* OEPA DERR site records; source-water assessments.

## Claim 3 — a documented PFAS (AFFF) groundwater plume on that aquifer

**Profile assertion:** the PFAS component of the header-comment plume phrase (above), `[inference]`.

**Status: to-verify `[open]`.** Verify against the **primary environmental record**:

- **DoD / Air Force PFAS (AFFF) record** — WPAFB is on the DoD PFAS-investigation list (aqueous
  film-forming foam at fire-training areas); pull the DoD/AF PFAS site inventory and any preliminary
  assessment/site inspection (PA/SI). *Instrument:* DoD PFAS site list; AF PFAS reports.
- **ATSDR** — any PFAS health consultation / public-health assessment for WPAFB groundwater.
  *Instrument:* ATSDR site records for Wright-Patterson AFB.
- **Ohio EPA (OEPA)** — DERR / drinking-water records for the affected well fields; source-water
  protection area delineations. *Instrument:* OEPA DERR site records; source-water assessments.

## The overlay as an analysis dimension

Once verified, define a **buried-valley + plume overlay**:

- **Supply denominator** = the well-field / aquifer capacity (not in-stream 7Q10). A sited campus's
  consumptive draw screens against **groundwater supply** and **source-water protection areas**.
- **Contamination overlay** = the TCE + PFAS plume footprints intersecting the sole-source aquifer
  and the well-field capture zones. A new large groundwater withdrawal near a plume can **alter
  capture zones / mobilize contamination** — the screening question is siting relative to the plume,
  not dilution.
- **Cross-site link:** the same buried-valley aquifer underlies **Xenia/Beavercreek** (#460) — the
  plume overlay is shared corridor context, not Lima's.

This overlay is **not covered by the surface Tier-0 tools** and is filed as a **new dimension** to
build once Claims 1–3 are verified.

## Open items (blocking promotion of either claim to a finding)

1. `[open]` US-EPA SSA designation record for the Buried Valley Aquifer System (FR notice + area).
2. `[open]` USGS/ODNR buried-valley hydrogeology + well-field dependence.
3. `[open]` AF IRP / CERCLA administrative record for the TCE plume (OUs, RODs).
4. `[open]` DoD/AF PFAS (AFFF) site record + PA/SI.
5. `[open]` ATSDR health consultation (if any).
6. `[open]` OEPA drinking-water / source-water-protection-area records for the well fields.

Until each is cited, the `SiteProfile` tags (`[inference]`/`[reference]`) stand — **not upgraded to
`[verified]`.**

## Sources (to pull — none yet in the BOSC corpus)

- US-EPA Region 5 Sole Source Aquifer program (Safe Drinking Water Act §1424(e)).
- USGS — Great Miami Buried Valley Aquifer System reports.
- Miami Conservancy District — Great Miami Buried Valley Aquifer monitoring.
- US Air Force / AFCEC — WPAFB Installation Restoration Program administrative record (TCE).
- DoD — PFAS site inventory (WPAFB AFFF).
- ATSDR — Wright-Patterson AFB site records.
- Ohio EPA — DERR + drinking-water source-water assessments.
- In-corpus context: `data/research/onboard-wpafb-*/findings.md`; profile `_WPAFB.hsg_citation`.
