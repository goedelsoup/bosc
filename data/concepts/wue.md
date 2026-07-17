---
title: WUE
kind: term
aliases: [water usage effectiveness]
tags: [data-center, water]
summary: A data center's water use per unit of IT energy — the cooling-water efficiency ratio; whether it counts withdrawal or consumption depends on how it is reported, so the basis has to be recorded before the number is used.
related: [pue, consumptive-cooling, hyperscale-data-center]
---

**Water usage effectiveness** measures a data center's cooling-water use against the
energy delivered to its IT equipment, usually stated in liters per kilowatt-hour. It is
the water peer of [[PUE]]: where PUE captures energy overhead, WUE captures how much
water the cooling system uses to reject the resulting heat. The convention counts
on-site *consumption*, but a reported WUE may instead be built on *withdrawal* — a
distinct quantity — so the metric basis has to be recorded, not assumed.

WUE is the coefficient that turns a computing load into a cooling-water quantity, which
is why it is central to the water thread. An evaporative, [[closed-loop cooling]] design
posts a higher WUE — it spends water to save electricity — while an air-cooled or
[[once-through cooling]] design posts a lower one. Multiplying a facility's IT energy by
a WUE yields that water quantity on the metric's own basis; getting to the
[[consumptive cooling]] draw the water-balance model tests against a reach's low flow
takes a further, separately labeled withdrawal-to-consumption assumption when the WUE
is a withdrawal figure. Because operators report WUE inconsistently, the platform
carries it as a labeled scenario input, not a measured fact.
