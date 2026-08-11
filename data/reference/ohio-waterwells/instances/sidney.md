---
site: sidney
title: The well census at Sidney — Shelby County, OH
---

Sidney's copy of the [Ohio well-log census](../README.md):
`reference/ohio-waterwells/shelby.csv`, pulled with `watermark waterwells --county Shelby`
for issue #1997. Every figure below was counted off the committed CSV — nothing here is
fabricated, inferred, or estimated by BOSC.

## Headline (last pull)

**3,776** logged wells. By **use**: 2,036 Domestic · 152 Agric/Irrig · 84 Monitor · 23
Public/Semi-Public · 22 Observation · 13 Municipal · 13 Dry/No Water · 10 Heating/Cooling ·
10 Industrial · 1,367 unrecorded. **2,036 domestic wells is the private-well population
behind any "area well concerns" here.**

The screen the study runs on it reduces the census to the dominant **limestone** aquifer and
puts a hypothetical groundwater stress through a Theis cone: **318** domestic wells fall
within the `[inference]` radius of influence of the campus point.

## ⚠️ None of the 13 MUNICIPAL wells is the City of Sidney's

They belong to Jackson Center, Fort Loramie and other village systems. Sidney's own
municipal wells are identified through Ohio EPA's protection-area geometry and the City's
GIS, **not** through this file's `MUNICIPAL` use code — and its four-to-five bedrock
production wells do not appear in the census at all (zero logged wells inside their inner
management zone). Reading the use code as a roster of city wells would get the City's supply
wrong in both directions.

What the census *does* give directly is the **Washington Township** field: three
sand-and-gravel production wells at 79 / 122 / 132 ft, cased 59 / 97 / 103 ft, static water
level **8.6 / 8.9 / 8.6 ft** below surface, reported test rates 1,500 / 1,102 / 1,999 gpm.

## What this census is not evidence about

It is a county population of wells. It says nothing about the campus's own aquifer setting,
which is the **Union City End Moraine** (yield 5–25 gpm) and sits **1.68 miles outside** the
designated sole-source aquifer — see
[`data/extracted/sidney/groundwater.md`](../../../extracted/sidney/groundwater.md). The
sole-source framing that once attached to this campus is refuted; the designation is a
finding about one of the City's two well fields, not about the site.
