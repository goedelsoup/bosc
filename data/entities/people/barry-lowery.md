---
name: Barry Lowery
slug: barry-lowery
entity_key: BARRY LOWERY
aliases: [Barry Lowery]
roles: [permit contact]
affiliations: [Google]
summary: Person to Contact of record on the 2026-08-14 BOSC-1A sanitary PTI (DSWPTI-260597).
expanded_research: false
sources:
  - data/extracted/permits/4230060.epa.yaml
  - data/extracted/permits/4074527.epa.yaml
tags: [bistrozzi, permit-contact]
---

## How he appears in the record

One document, one role. Ohio EPA Permit to Install **DSWPTI-260597**, issued and effective
**2026-08-14** (eDoc `4230060`, p1), names under *Person to Contact*:

> Person to Contact: Barry Lowery · Email Address: **`barrylowery@google.com`** ·
> Phone Number: Business: (650) 254-3045

The applicant on the same page is **Bistrozzi LLC**, 4110 N Cole St, Lima.

## The delta this records

This is a **change in the contact of record** between the two generations of the same
private-sanitary permit, and the change is the whole of the finding:

| | `4074527` — DSWPTI-260294 (2026-04-07) | `4230060` — DSWPTI-260597 Rev. 1 (2026-08-14) |
|---|---|---|
| From / Person to Contact | Scott Ziance | **Barry Lowery** |
| Contact e-mail | `MBEINE@EMHT.COM` (EMH&T) | **`barrylowery@google.com`** |
| Phone | — | (650) 254-3045 |

⚠️ **What this establishes, exactly.** That a Google employee is the applicant's contact of
record on an issued Ohio EPA permit. `[verified]` — both documents are in the corpus and both
lines were read from the documents themselves.

⚠️ **What it does not establish.** Ownership, tenancy, corporate control, or that Google is the
AEP "Lyka" customer. Those remain `[inference]` pending the OPSB docket (#1476). A contact of
record evidences **who fronts a filing** and nothing further. Note also that the **application**
for this same permit (eDoc `4230068`, 2026-05-27) still carries the EMH&T submitter address
`MBEINE@EMHT.COM` — the change appears on the issued permit, not on the filing that requested it,
which narrows the claim further rather than widening it.

The only other `@google.com` applicant contact anywhere in `data/extracted/` is Randy Barrera on
`permits/dazzler-permits/4081890.epa.yaml` — a **different site**. A second one, Michael Smith
(`smithmif@google.com`, Facility Manager), appears on the `2DP00130` indirect-discharge
application package, which is not yet ingested (#2089).

## Research status

**Not expanded.** `expanded_research: false` keeps this profile off the published site. The
underlying fact is on a public agency record, but publishing a named individual's work contact
is its own reviewed decision under `docs/legal/document-publication-review.md` (#274/#281), not a
side effect of an ingest. Nothing beyond the permit line above has been researched, and the
affiliation is read from an e-mail domain on one document — cited, and no stronger than that.

> Roles read from public records are *common-control plumbing* and leads to verify —
> **not** statements about beneficial ownership or wrongdoing.
