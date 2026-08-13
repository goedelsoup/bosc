# `sidney/ordinances/` — City of Sidney land-use ordinances

The instruments that brought the AWS campus ground into the City and told it what it may be. Pulled
2026-08-13 for the tail of [#1998](https://github.com/watermark-directory/the-watermark-directory/issues/1998).

| File | What it carries |
|---|---|
| `A-3225 - Annexing 243.092 Acres - Joslin-Drees.pdf` | The annexation. ⚠️ Cites **no R.C. 709 provision** — its authority is a City/Clinton Township Annexation Agreement of ~2025-03-24 that is not in this corpus |
| `A-3226 - Zoning 243.092 IIM - Joslin-Drees Annexation.pdf` | **The zoning: IIM — Industry / Innovation / Manufacturing.** Closes an `[open]` carried since onboarding |
| `A-3210 - New Zoning Map, Sidney, Ohio.pdf` | Why the City's GIS could not answer that question: the official map "incorporates all the rezoning, annexation, or detachment ordinances from July 25, 2022, to **January 13, 2025**" |

Both land ordinances passed the same night, **2025-07-28**.

## Read these with the Planning Commission minutes

They are not the whole act. Six weeks before Council passed A-3226, the City's own Planning
Commission was asked to recommend that zoning and **declined, 0–4** — see
[`../planning-commission/`](../planning-commission/). A-3226 carries no WHEREAS clauses and does not
mention the Commission, so the ordinance alone cannot tell you that happened.

## Source and route

The City's Documents-On-Demand portal, over **HTTP/1.1** (the identical request returns 403 over
HTTP/2 — the fingerprint block described in [`../council/filename-map.yaml`](../council/filename-map.yaml)).
Container: City Council → Legislation → **Ordinances**, guid `a69a9b5a-0bff-45c3-ba90-08d1ffd71296`,
**51 year folders back to 1976**.

As-received names, SHA-256, page counts and how each date was content-verified are in
[`filename-map.yaml`](filename-map.yaml). Every hash there was **independently reproduced by a
second pull** before shelving.

## What is not here yet

The 2025 ordinances for the separate 53-acre Shelby County Commissioners tract (**A-3211**,
**A-3227** — a different tract in the southeast quarter of the same section, *not* the campus), the
zoning-code ordinances that define the IIM use list (**A-3219**, **A-3236**, **A-3255**), and the
current official map (**A-3270**). All are read and hashed; they land in a following change.
