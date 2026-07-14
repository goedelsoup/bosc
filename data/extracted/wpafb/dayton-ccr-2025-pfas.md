# City of Dayton 2025 Water Quality Report — finished-water PFAS

Provenanced extraction of the PFAS table from the City of Dayton **2025 Water Quality
Report** (Consumer Confidence Report), the SDWA-required annual report for the Dayton
public water system that draws the **Buried Valley sole-source aquifer** (the same aquifer
[verified] at [53 FR 15876](ssa-53fr15876.epa.yaml) and contaminated at
[the WPAFB CERCLA site](cercla-ffa-1991.epa.yaml)).

- **Source:** `data/documents/wpafb/ccr/2025-Water-Quality-Report.pdf`
  (City of Dayton, DocumentCenter/View/17424; retrieved 2026-07-14). Figures read from the
  PDF text layer (`pdftotext -layout`), not the filename.
- **Plants:** Dayton operates two treatment plants — the **Ottawa** plant and the **Miami**
  plant — supplied by the **Miami** and the **Mad River** well fields.

## Finished-water PFAS, 2025 running annual averages (ppt = ng/L) — `[verified]`

| Analyte | Ottawa Plant avg (range) | Miami Plant avg (range) | MCL | MCLG |
|---|---|---|---|---|
| PFOA (Perfluorooctanoic Acid) | 2.976 (`<2.0`–4.5) | `<2.06` (`<2.0`) | 4.0 | 0 |
| **PFOS (Perfluorooctanesulfonic Acid)** | **8.816 (5.45–13.67)** | `<2.06` (`<2.0`) | 4.0 | 0 |
| **PFHxS (Perfluorohexanesulfonic Acid)** | **13.536 (6.70–23.32)** | `<2.06` (`<2.0`–2.67) | 10 | 10 |
| PFBS (Perfluorobutanesulfonic Acid) | 2.726 (`<2.0`–3.61) | 2.636 (`<2.0`–4.09) | — (Hazard Index) | — |

`[verified]` **The Ottawa plant's 2025 running annual averages EXCEED the 2024 PFAS National
Primary Drinking Water Regulation MCLs for PFOS (8.816 vs 4.0 ppt) and PFHxS (13.536 vs
10 ppt).** The Miami plant is non-detect / below MCL for both. Units are parts per trillion
(ppt), equivalently ng/L; MCLs are the finished-water maximum contaminant levels
(PFOA 4.0, PFOS 4.0, PFHxS 10, GenX 10 ppt).

## Monitoring history (context) — `[reference]`

The CCR narrative records that Dayton found PFAS detections in monitoring wells in the
**Tait's Hill and Huffman Dam areas of the Mad River Wellfield** and near a "Training
Center," and has monitored finished water at both plants monthly since 2018; all finished
water had been below the 2016 health-advisory limit of 70 ppt until the 2024 rule's lower
MCLs took effect. (The Mad River Wellfield / Huffman Dam area is downgradient of WPAFB — the
plume-to-supply link the CERCLA FFA and USGS SIR 2023-5017 address; the precise
wellfield → plant supply mapping is not asserted here from the CCR text alone.)

## Provenance / discipline

- This is a **supporting extraction**, not one of the record-domain's classified
  `permits-epa`/`permits-npdes` records — the CCR is a utility monitoring report, not a
  permit/agency-action genre. It is catalogued under the `wpafb` extracted dataset and its
  source PDF is committed to `data/documents/wpafb/ccr/`.
- Figures are the utility's own published finished-water results; the exceedance statement is
  a direct read of the reported averages against the printed MCLs, not an inference.
