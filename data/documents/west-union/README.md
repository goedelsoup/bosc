# `west-union/` — Adams County, Ohio (Buck Canyon)

**Collection:** the West Union site's own records · immutable source evidence

The site slug names the county seat; the project is 15 miles away in the county's far
south-west corner, on the Ohio River. See
[`data/extracted/west-union/data-centers.md`](../../extracted/west-union/data-centers.md)
for the campus record this corpus supports.

## Layout

| Subfolder | What |
|---|---|
| [`acrwd/`](acrwd/) | Adams County Regional Water District — the public utility that will supply the campus. Governance, board minutes, finance, and the Ginger Ridge instruments. |

The federal §404 file for the same campus is a sibling under
[`usace/west-union/`](../usace/west-union/), filed by issuing agency the way
`oepa/<slug>/` and `idem/<slug>/` are. Both are inside this site's corpus scope, which is
derived from the slug (`west-union/` **and** `*/west-union`) — see
`watermark.sites._eponymous_prefixes`.

## Why the water district is the first record here

Adams County is **essentially unzoned**, and Sprigg Township's 2026-03-02 "voluntary
moratorium" carries no land-use force. There is no local approval in this project's path —
no council vote, no rezoning, no conditional-use hearing, and therefore none of the
legislative record that carries the story at Sidney, Bowling Green or Van Wert.

What the county does have is a **regional water district**: a body created by court order
under R.C. Ch. 6119, whose nine trustees are appointed rather than elected, and which is the
only local public entity that had to say yes to anything. Its board minutes are, so far as
this corpus can establish, the only local public record of the project's progress. That is
why an obscure utility's meeting file is the first thing shelved for this site.

## What the record shows, in one line each

- **2024-01-10/11** — the General Manager signs a nondisclosure agreement with a company the
  document never names; the Board authorizes it the next day.
- **2024-10-10** — the codename **"Project Galaxy"** appears; the engineer has already been
  working on it *without a contract*.
- **2025-04 / 2025-05** — new wells, a treatment-plant expansion and a transmission main to
  the former J. M. Stuart Station / Carter Hollow; an interim line from Ginger Ridge Road
  for potable **and supplemental cooling water**, sized at **100,000 gallons per day**.
- **2025-10-09** — the codename is retired: "Ginger Ridge Water Line and Tank (formerly
  Project Galaxy)". The customer wants the design *fast-tracked*.
- **2025-12-11** — the client **deletes the tank**; a meter vault replaces the storage the
  District wanted.
- **2026-04 → 2026-07** — plans to Ohio EPA, review complete, approval letter pending.

## ⚠️ "Project Galaxy" is not an identifier

This is now the **third** county whose records attach that name to a data-center project.
The corpus already holds the collision between Sidney (Shelby County, where local and trade
press use it for a campus Ohio EPA calls "Sidney Data Center Campus" / the City calls
"Project Rey") and **Fayette County**, where "Project Galaxy" is a live Ohio EPA *facility
name* — see [`data/extracted/sidney/data-centers.md`](../../extracted/sidney/data-centers.md)
and `regulatory-watch.yaml` there.

Adams County's water district is the third. **Nothing in this corpus establishes that any
two of the three are the same project**, and the ACRWD minutes never explain where the name
came from. Treat "Project Galaxy" as a codename in local use, never as a key — join on
instrument numbers, parcels and coordinates instead.

## What is not here yet

The Common Pleas entry that created the District (**Adams County Case No. 930355**, filed
1994-01-10, recited in the 1994 by-laws but not held); the Ohio EPA plan-approval letter for
the Ginger Ridge main; the executed easements; and — the significant absence — **any service
agreement or contract between the District and the customer**. The corpus holds the
District's engineering and its confidentiality obligation, and not the deal.

Roughly half the monthly board minutes between 2024-01 and 2026-07 are also absent; see the
`gap:` note in [`acrwd/minutes/filename-map.yaml`](acrwd/minutes/filename-map.yaml).

## Publication status

⚠️ **Nothing in this collection is cleared for publication.** Two files carry names of
private individuals — the 1993 election roster with home addresses
(`acrwd/governance/1993-1998 Elections-Appointments.pdf`) and the plan set's route-parcel
owner labels (`acrwd/ginger-ridge/Ginger Ridge Water Line Plan.pdf`). Both are flagged in
their `filename-map.yaml` under `pii:`. Neither has a `review:` decision, and none should be
added to `data/site/published-documents.yaml` without one.
