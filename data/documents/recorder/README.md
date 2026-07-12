# Recorder filings — deeds, notices & conveyances (original records)

**Collection:** `recorder/` · immutable source evidence

Allen County Recorder instruments (deeds, notices, conveyances) for the
BOSC-corridor parcels. Raw bytes are never edited; structured reads live in the
mirrored [`data/extracted/recorder/`](../../extracted/recorder/) as
`*.deed.yaml` / `*.notice.yaml`.

## Layout

| Subfolder | What |
|---|---|
| [`bistrozzi-deeds/`](bistrozzi-deeds/) | Bistrozzi-entity deeds (5 instruments). |
| [`bistrozzi-notices/`](bistrozzi-notices/) | Bistrozzi-entity lien-priority notices (R.C. 1311.04 Notices of Commencement). |
| [`port-authority/`](port-authority/) | Port-authority conveyances (e.g. `…-amazon-deed.pdf`). |

Files are named by the Recorder's **instrument number** (e.g.
`202508130008300.pdf` = recording date + sequence). Keep the as-received names —
the instrument number is the authoritative handle.
