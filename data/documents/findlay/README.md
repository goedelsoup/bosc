# Findlay, OH — site source documents (original records)

**Collection:** `findlay/` · immutable source evidence

Primary instruments specific to the Findlay watershed point (Hancock County, Blanchard River)
that are not Ohio EPA permits — those live in [`../oepa/findlay/`](../oepa/findlay/). Raw bytes are
never edited; structured reads live in [`data/extracted/findlay/`](../../extracted/findlay/).

## Contents

### `warn/` — ODJFS WARN Act notices

Two filed plant-closing notices for Findlay facilities, both served from the Ohio DAM's
`jfs.ohio.gov/warn/` tree.

| File | Employer | Filed | Jobs |
|---|---|---|---|
| `GoodyearTireRubberCompany.pdf` | The Goodyear Tire & Rubber Company — Tall Timbers Mold facility, 2025 Production Drive | 2026-01-30 | 85, permanent |
| `Michigan_Sugar_Company.pdf` | Michigan Sugar Company — warehouse, 1343 Greenwood Street | 2025-12-11 | 4, courtesy filing |

The Michigan Sugar letter is a **courtesy** filing — the company states it does not believe the
closure required notice — and its stated rationale puts a severed rail spur at the Findlay site on
the record. Structured reads:
[`warn/goodyear-tall-timbers-mold-2026.warn.yaml`](../../extracted/findlay/warn/goodyear-tall-timbers-mold-2026.warn.yaml),
[`warn/michigan-sugar-findlay-2025.warn.yaml`](../../extracted/findlay/warn/michigan-sugar-findlay-2025.warn.yaml).

### `brownfield/` — Ohio Brownfield Remediation Program

`Round 11 Brownfield Descriptions.pdf` — the statewide Round 11 award-description packet (53 pp.)
distributed with the 2026-05-13 announcement. Three of its entries are Hancock County, totalling
$999,998: the former Lincoln Elementary School remediation ($663,998, City of Findlay), the Tiffin
Avenue abandoned gas-station assessment ($238,000, City of Findlay), and the Bluffton former Gas
America assessment ($98,000, **Hancock County Commissioners Office**). Structured read:
[`brownfield/round-11-hancock-2026.award.yaml`](../../extracted/findlay/brownfield/round-11-hancock-2026.award.yaml).

## Source & provenance

Retrieved 2026-07-31 (issue 1460). Per-file source URL, sha256, byte count and fetch time are in
each sub-directory's `filename-map.yaml`.

## Caveats

- The Round 11 packet is served without a `Content-Disposition` header, so the only name on the
  wire is the percent-encoded URL path segment. It is stored **URL-decoded** — that decode is the
  attachment's actual name, not a correction of it — and both forms are recorded in
  [`brownfield/filename-map.yaml`](brownfield/filename-map.yaml). The bytes are untouched.
- The Round 11 total is **Round 11 only**. Hancock County's presence in Rounds 4-10 is unresearched
  and this collection says nothing about it.
- The Goodyear letter names no destination for the closed facility's work and no labor organization.
  Do not source either from this collection.
