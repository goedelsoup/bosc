# Allen County Commissioners minutes & agendas — RETIRED to the civic connector

**Collection:** `commissioners/minutes/` · superseded by [`commissioners/meetings/`](../meetings/)

The hand-assembled `raw/` tree (930 PDFs) was **retired in the #133 cutover
(2026-06-12)**. The Board of Commissioners' full meeting record — minutes + agendas,
Jan 2023– — is now **connector-sourced** under
[`data/documents/commissioners/meetings/`](../meetings/), pulled via the civic
pipeline (`watermark subdivisions download commissioners`).

Every retired `raw/` file was verified **byte-identical** to its connector copy before
removal — the only deletion the chain-of-custody rule permits (a checksum-verified
byte-identical duplicate). The per-file record (930/930 matched, 0 retained) is
[`cutover-reconciliation.yaml`](../../../extracted/commissioners/meetings/cutover-reconciliation.yaml);
the original bytes also remain in git/LFS history and are re-acquirable from the county
site.

## Nothing to re-cite

Citations are by **bare filename** (`M021926.pdf:3`) and resolve unchanged under
`meetings/` — the as-received names are identical. The as-received-name alias layer
(typo'd / long-form names) and the standing completeness audit live in
[`data/extracted/commissioners/minutes/`](../../../extracted/commissioners/minutes/README.md)
(`filename-map.yaml`, now carrying the `civic_cutover` record); the source PDFs they
describe now live in `meetings/`.

## Filename convention (unchanged)

`[AM]MMDDYY` — `A011624` = agenda 2024-01-16, `M…` = minutes. The **filename is the
meeting date** (not the upload path). Three typo'd names map to real dates —
`A0101024` → Oct 10 2024, `A0404024` → Apr 4 2024, `M0115226` → Jan 15 2026 — recorded
non-destructively in `filename-map.yaml`.
