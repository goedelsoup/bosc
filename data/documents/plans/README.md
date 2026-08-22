# Engineering plans / drawings (original records)

**Collection:** `plans/` · immutable source evidence

Engineering plan sets, drawings, and engineering reports for the BOSC-corridor
build-out. Raw bytes are never edited; structured reads live in the mirrored
[`data/extracted/plans/`](../../extracted/plans/).

## Layout

| Path | What |
|---|---|
| [`bistrozzi-plans/`](bistrozzi-plans/) | Bistrozzi plan sheets — e.g. `LMA1A-95-SPS-2025-10-28.odg` (an OpenDocument Drawing storm/site sheet, read via `watermark.documents.odg`). |
| `4091286.pdf` | Storm Water Pollution Prevention Plan (**SWP3**) for the **Beery Rd. & Cole St. roundabout / BOSC Storm Outfall** — operator George J. Igel & Co., engineer WSP USA; Ohio EPA eDocument ID kept as the as-received handle, read as `4091286.engineering.yaml` (`kind=engineering`). |
| `4091289.pdf` | Ohio EPA **NPDES CGP Approval Letter** (eDoc 4091289, April 22, 2026) — the SWP3's Appendix A authorization: Facility Permit Number **`2GC08747*AG`**, effective 2026-04-22 under OHC000006. Companion to `4091286.pdf`. |
| `4091285.pdf` | Ohio EPA **Notice of Intent (NOI)** for coverage under the construction-stormwater general permit (eDoc 4091285, 2 pp, 2026-04-22) — the fourth and last document under Facility Permit Number `2GC08747`, and the application the `4091289.pdf` approval letter answers. Fetched 2026-08-22 from the eDocument portal (`ViewDocument.aspx?docid=4091285`, sha256 `bc44ff4d…`); the portal supplies no filename, so the bare eDocument ID is used to match its three companions above rather than the `edoc-<docid>.pdf` form `data/documents/oepa/<slug>/` uses — see #2073. |
| `4091287.pdf` | SWP3 appendix sheet (eDoc 4091287) — NRCS soils / contaminated-soils / on-site-streams page confirming the outfall terminus (Point 1: **Pike Run**). Companion to `4091286.pdf`. |

`.odg` is a vector drawing format; see [`data/extracted/plans/`](../../extracted/plans/)
for the parsed storm-inventory, plan, and engineering extractions.
