# legal/thor-v-urbana/ — Thor Equities v. City of Urbana (federal)

Source filings for the **Thor Equities et al. v. City of Urbana** litigation over the zoning
reversal that halted the **Urbana Technology Hub** data-center campus (site: urbana). This is
the live legal spine of the Urbana data-center story (epic #1263, sub-issue #1329) and is kept
**distinct** from the network-global Allen-County records-mandamus track
(`docs/legal/mandamus-analysis.md`): this is a **takings / vested-rights / zoning-reversal**
posture, not a records-mandamus.

## Source

| Doc | Case | Filed | What |
|---|---|---|---|
| `1.pdf` | **3:26-cv-00196-MJN-CHG** (S.D. Ohio, Western Div.) | 2026-06-19 | Complaint (37 pp, 8 counts, jury demand) |

Retrieved as the native ECF/PACER document (Document No. 1); kept under its as-received
docket-document number per chain of custody. Canonical name + SHA-256 in
[`filename-map.yaml`](filename-map.yaml). Content-verified from the PDF text layer, 2026-07-10.

## Reviewed extraction

The structured read (docket, parties, counsel, the eight counts, the prayer, the recited
ordinance/moratorium record, and the zoning + litigation timeline) lives with the Urbana
site synthesis, not here:

- [`data/extracted/urbana/litigation-thor-v-urbana.yaml`](../../../extracted/urbana/litigation-thor-v-urbana.yaml)
- [`data/extracted/urbana/litigation-thor-v-urbana.md`](../../../extracted/urbana/litigation-thor-v-urbana.md)

## Known gaps

- **Exhibits 1–9 are not in Doc #1** (separate ECF attachments): Ordinances 4619-25, 4625-25,
  4620-25, 4621-25, 4635-26; Resolution 2727-26; the Apr-10-2026 counsel letter; the BZA
  response; and Thor's motion for continuance. The ordinance/resolution facts below are
  therefore **recited by the complaint** — the instruments themselves stay `[open]`.
- **The Champaign County Common Pleas administrative appeal** (Thor's appeal of the BZA
  "incomplete" determination — the second case named in #1329) is referenced in the complaint
  (¶¶71–72) but **not yet ingested**; its case number is `[open]`.
