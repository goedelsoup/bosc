# PRR production batch 3 — Sanitary Engineer per-item trees (received 2026-07-24)

**Collection:** `legal/prr-mandamus/` · immutable source evidence

The Allen County Sanitary Engineering department's per-item production for county
records-request items 9, 11, 13, 14, 15, delivered via the Board of Commissioners on a
USB flash drive (volume "STORE N GO", folder "Sanitary Records 7:24") received
2026-07-24. Unlike batches 1–2 (assembled scan bundles), this is a **native
departmental file-tree copy**: 1,610 files / ~1.04 GB of original Word/Excel/PDF/
image/media files with as-received names, folder structure, and file-server
modification times (2003–2026) intact.

Raw bytes are never edited. The reviewed artifacts live in the mirrored
[`data/extracted/legal/prr-mandamus/`](../../../../extracted/legal/prr-mandamus/):
the per-file custody record (sha256 · bytes · as-received mtime · request item ·
duplicate group) is
[`bosc-prr-production-2026-07-24.custody-manifest.yaml`](../../../../extracted/legal/prr-mandamus/bosc-prr-production-2026-07-24.custody-manifest.yaml),
and the item-by-item requested-vs-produced posture is
[`bosc-prr-production-2026-07-24.response-index.yaml`](../../../../extracted/legal/prr-mandamus/bosc-prr-production-2026-07-24.response-index.yaml).

## Layout (as received)

| Folder | Request item | What |
|---|---|---|
| `9/` | Item 9 — Shawnee II Phase 2 capacity justification | "SH & AB SSO Findings and Orders": SSO enforcement + Phase 1 SECAP construction (Shawnee force main incl. the Ottawa River crossing, Shawnee–Ft Amanda pump station, American-Bath trunk sewer), WPCLF/EPA Loan No-6718 financing, 2019 SSO reports, photos/video and a 2015-09-18 audio recording. 1,236 files. |
| `11/` | Item 11 — feasibility study + WPCLF application | A single `WPCLF Application.pdf`: Hume Road Sewer System, $1.76M, dated 3/1/2026. |
| `13 - See 9/` | Item 13 — MS Consultants records 2024→ | Empty; the county's own foldername cross-references item 9. |
| `14/` | Item 14 — Cridersville agreement review/termination | "Shawnee Oaks": the 2014 Cridersville treatment agreement + renewal, 1997 correspondence, and the live 2026 reroute to Shawnee WWTP (Buchanan land purchase, easements, WPCLF financing, property-owner database). 40 files. |
| `15/` | Item 15 — 1996 CWA consent decree + DFFOs | "Directors Final Findings & Orders": 2005 DFFO correspondence, 2014 Modified DFFO (+ 5-yr-extension revision, OEPA email threads), the 2023-02-02 Shawnee II DFFO extension letter, SECAP record. 333 files. |

## Custody notes

- **As-received names/tree kept verbatim** — including `Thumbs.db` files, `_Redacted`
  PDFs (county redactions applied at production time), three extensionless files, and
  the county's own item-9↔15 filing overlap (411 byte-identical duplicate groups,
  recorded in the custody manifest — nothing was deduplicated or renamed).
- **Excluded from the copy:** `._*` AppleDouble files and `.DS_Store` — created by the
  requester's macOS mounting the FAT-formatted drive on 2026-07-24; not part of the
  county's production.
- **mtimes:** git does not retain modification times; the as-received timestamps are
  recorded per-file in the custody manifest. The USB drive is retained as the original.
- **File modes:** the FAT-formatted drive synthesizes `rwx` permission bits; those are
  a filesystem artifact, not part of the production — git modes are normalized to 644.
  Content bytes, names, and structure are verbatim.
- Paths run to ~290 characters with spaces/`&`/`#` — on Windows, clone with
  `core.longpaths=true`.
