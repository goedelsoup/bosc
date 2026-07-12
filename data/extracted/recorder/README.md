# Recorder deed & notice extractions

Reviewed structured reads (`*.deed.yaml`, `*.notice.yaml`) of the Allen County
Recorder instruments under
[`data/documents/recorder/`](../../documents/recorder/README.md). One file per
instrument, named by the Recorder instrument number.

## Conventions

Grantor/grantee, parcels, consideration, and dates are read from the deed image/text
and never inferred. Each file records `doc_id`, `source_path`, `pages_read`, and a
provenance block. The `…-amazon-deed` file is the port-authority conveyance.

`202606250006699.notice.yaml` is a Notice of Commencement (R.C. 1311.04, `kind:
notice`) — a lien-priority filing, not a conveyance, so it carries a project/
footprint/contractor/contract-date shape (`watermark.models.NoticeOfCommencement`)
instead of a grantor/grantee shape. Its attached exhibit re-records three
already-committed Bistrozzi deeds (202508130008300, 202508130008316,
202508130008312); only the notice's own substantive pages are extracted, and the
exhibit is cross-checked, not re-transcribed (see the file's `warnings`).
