---
title: PUE
kind: term
aliases: [power usage effectiveness]
tags: [data-center, energy]
summary: A data center's total facility energy divided by its IT-load energy — the standard measure of how much overhead (mostly cooling) its computing carries.
related: [wue, hyperscale-data-center, consumptive-cooling]
---

**Power usage effectiveness** is the ratio of a data center's total energy use to the
energy delivered to its IT equipment. A PUE of 1.0 would mean every watt reached the
servers; real facilities land above that, and the gap is overhead — chiefly cooling and
power conversion. A modern efficient campus reports a PUE near 1.1–1.2.

PUE is the lever that connects computing to cooling, and through cooling to water. A
lower PUE means less energy spent moving heat, but the efficient designs that achieve
it often lean on evaporative [[consumptive cooling]], trading electricity for water —
which is why PUE and its water counterpart, [[WUE]], have to be read together. The
platform treats an operator's reported PUE as a claimed [reference] figure, useful for
scaling a [[hyperscale data center]]'s total draw from its IT load but not a
substitute for the actual metered demand.
