# `reference/west-union/` — committed reference data for the West Union site

## `parcel-assemblage.geojson`

**Source:** Adams County, Ohio GIS — `Parcel_Layer` FeatureServer layer 4 (`MasterParcel`), org
`eFMIGXUWac5mgGdc`, the org behind the county's own hub at `acgis-adamso.hub.arcgis.com`.
**Pulled:** 2026-08-16 (#2049) · **CRS:** EPSG:4326 (WGS84) · **Features:** 2

### Regenerate

```sh
watermark --site west-union parcels \
  --parcel 1830000079000,1830000070002 \
  --geojson data/reference/west-union/parcel-assemblage.geojson
```

⚠️ Note the `--parcel` form. The usual `--owner <assembler>` recipe **cannot work here** — this
layer has no owner column, so `parcels_geojson_by_owner` refuses cleanly. The by-number path
exists for exactly this case.

### What the two parcels are

| Parcel | Deeded | Planar | Role |
|---|---|---|---|
| `1830000079000` | **1016.2174 ac** | 1009.50 ac | **The Buck Canyon campus** — Sprigg Township, the former DP&L landfill north of the retired J.M. Stuart Station |
| `1830000070002` | 2.125 ac | 2.17 ac | Buck Canyon Properties, LLC's small holding on the ACRWD Ginger Ridge water-main route, ~1 km north of the campus |

**How the campus parcel was identified:** point-in-polygon against the coordinate the U.S. Army
Corps published in its own Section 106 correspondence — **38.646748 / -83.659828**
(`data/documents/usace/west-union/Email Chain 11.pdf` p.0) — which falls inside exactly one parcel.

**And then the acreages matched.** The county carries two, and both of the Corps' figures are
among them:

- deeded **1016.2174 ac** ↔ "encompasses approximately **1,016 acres**" — `[verified]`
- planar **1009.50 ac** ↔ "limits of disturbance … approximately **1,009 acres**" — `[inference]`,
  consistent with the consultant measuring off the same geometry, but nothing says so

**One tract, not an assemblage.** There is no multi-seller land roll-up to trace here, unlike
Sidney, Wilmington, Bowling Green or Van Wert. The ~1,016 acres was already a single parcel.

## ⚠️ Read this before quoting a null

Adams County serves a **tax-map** layer: geometry, parcel number, two acreage columns, township,
and a path to the surveyor's plat PDF. It has **no CAMA join** — no owner, no owner mailing name,
no situs address, no conveyance date, no sale amount, no valuation, no land-use code. The
`CAMA_LINK` column exists and is blank on every row sampled, including the campus parcel.

So the committed features carry `owner: null`, `situs_address: null`,
`owner_mailing_address: null` and `transfer_date: null` — **because the county publishes none of
them**, not because the parcel is unowned or was never sold.

This is a step past Findlay's OGRIP substitute, which is owner-redacted but still carries a
tax-bill mailing name. Here there is nothing.

**Who owns the campus is `[open]`.** See lead `ACRWD-CAMPUS-PARCEL-OWNERSHIP` in
[`data/site/west-union/leads.yaml`](../../site/west-union/leads.yaml). The routes are the Adams
County Auditor (`adamscountyauditor.org`, searchable by parcel number) for the CAMA record and the
Adams County Recorder for the deed.

## Right-county guard

At least nine other states have an Adams County, and several publish similarly-named parcel
layers — a hub search for "Adams County parcels" returns Pennsylvania and Colorado first. This
org is confirmed **Ohio's** three ways: it is the org behind the county's own GIS hub; its spatial
reference is **EPSG:3735** (NAD83 / Ohio South, ftUS); and the same org publishes a **VMS Boundary
Lines** layer — the Virginia Military Survey, the survey system of exactly this part of Ohio.

An earlier candidate found by hub search (`services2.arcgis.com/wEula7SYiezXcdRv/…/Parcel_Layer/11`)
was rejected: its extent converts to ~-120.4°, 37.2° — California — and its `APN`/`RS`/`PM` fields
are PLSS, not Ohio CAMA.
