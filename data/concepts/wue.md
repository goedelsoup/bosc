---
title: WUE
kind: term
aliases: [water usage effectiveness]
tags: [data-center, water]
summary: A data center's water consumption per unit of IT energy — the cooling-water efficiency ratio, and the bridge from a computing load to a withdrawal figure.
related: [pue, consumptive-cooling, hyperscale-data-center]
---

**Water usage effectiveness** measures a data center's water consumption against the
energy delivered to its IT equipment, usually stated in liters per kilowatt-hour. It is
the water peer of [[PUE]]: where PUE captures energy overhead, WUE captures how much
water the cooling system consumes to reject the resulting heat.

WUE is the coefficient that turns a computing load into a withdrawal, which is why it is
central to the water thread. An evaporative, [[closed-loop cooling]] design posts a
higher WUE — it spends water to save electricity — while an air-cooled or
[[once-through cooling]] design posts a lower one. Multiplying a facility's IT energy by
a WUE yields an estimate of its [[consumptive cooling]] draw, the number the
water-balance model tests against a reach's low flow. Because operators report WUE
inconsistently, the platform carries it as a labeled scenario input, not a measured
fact.
