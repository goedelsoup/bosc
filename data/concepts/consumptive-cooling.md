---
title: Consumptive cooling
kind: concept
aliases: [consumptive water use, evaporative cooling loss]
tags: [hydrology, data-center, water-balance]
summary: Cooling water that is withdrawn and lost (mostly to evaporation) rather than returned to the source, reducing downstream flow.
related: [assimilative-capacity, 7q10, hyperscale-data-center]
---

**Consumptive cooling** is the share of a facility's cooling-water withdrawal that
does not return to the watercourse — primarily evaporative loss from cooling
towers. Unlike a once-through return, a consumptive draw permanently removes flow
from the system downstream of the intake.

For a [[hyperscale data center]], the consumptive fraction of the cooling demand
is the quantity that matters to the river: it is subtracted from live flow in the
[[assimilative capacity]] screen against the [[7Q10]]. The water-balance model
treats the cooling demand and its consumptive fraction as scenario inputs
(labelled assumptions), while the receiving-water flows are read from live gauges
and the permit record.
